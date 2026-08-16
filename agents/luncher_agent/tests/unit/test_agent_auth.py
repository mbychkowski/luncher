"""Tests for the sub-agent credential flow (app.agent.GoogleAuth)."""

import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import agent as agent_mod

CLOUD_RUN_URL = "https://sched-agent.us-central1.run.app/a2a/app"
GOOGLE_API_URL = (
    "https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1"
    "/projects/1/locations/us-central1/reasoningEngines/2/api/a2a/app"
)


def _jwt(exp: datetime) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(exp.timestamp())}).encode()
    ).decode().rstrip("=")
    return f"header.{payload}.signature"


def _apply(auth: agent_mod.GoogleAuth, url: str = CLOUD_RUN_URL) -> httpx.Request:
    """Runs the async auth flow once and returns the request it produced."""

    async def run():
        request = httpx.Request("POST", url)
        flow = auth.async_auth_flow(request)
        prepared = await flow.__anext__()
        await flow.aclose()
        return prepared

    return asyncio.run(run())


class _FakeCreds:
    """Stands in for an ADC credential that applies itself to a request."""

    def __init__(self, token="adc-token", fail=False):
        self.token = token
        self.fail = fail
        self.calls = 0

    def before_request(self, request, method, url, headers):
        self.calls += 1
        if self.fail:
            raise RuntimeError("credential unavailable")
        headers["Authorization"] = f"Bearer {self.token}"


@pytest.fixture(autouse=True)
def _clear_adc_cache():
    agent_mod._adc.cache_clear()
    yield
    agent_mod._adc.cache_clear()


# --- JWT expiry parsing -----------------------------------------------------


def test_jwt_expiry_reads_exp_claim() -> None:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    parsed = agent_mod._jwt_expiry(_jwt(exp))

    assert parsed is not None
    assert abs((parsed - exp).total_seconds()) < 1


@pytest.mark.parametrize("token", ["not-a-jwt", "", "a.b", "a.!!!.c"])
def test_jwt_expiry_returns_none_for_unparseable_tokens(token) -> None:
    assert agent_mod._jwt_expiry(token) is None


# --- Google APIs: the credential applies itself -----------------------------


def test_google_api_calls_let_the_credential_apply_itself(monkeypatch) -> None:
    """The Agent Identity regression: reading creds.token yields a 401.

    Under Agent Identity there is no service account and the credential may not
    expose a usable bearer token, so it has to apply itself via before_request.
    """
    creds = _FakeCreds()
    monkeypatch.setattr(agent_mod.google.auth, "default", lambda scopes=None: (creds, "proj"))
    auth = agent_mod.GoogleAuth(GOOGLE_API_URL)

    request = _apply(auth, GOOGLE_API_URL)

    assert request.headers["Authorization"] == "Bearer adc-token"
    assert creds.calls == 1


def test_google_api_credential_is_reapplied_every_request(monkeypatch) -> None:
    """before_request refreshes internally, so it must run per request."""
    creds = _FakeCreds()
    monkeypatch.setattr(agent_mod.google.auth, "default", lambda scopes=None: (creds, "proj"))
    auth = agent_mod.GoogleAuth(GOOGLE_API_URL)

    _apply(auth, GOOGLE_API_URL)
    _apply(auth, GOOGLE_API_URL)

    assert creds.calls == 2


def test_google_api_request_is_unauthenticated_when_adc_fails(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod.google.auth, "default", lambda scopes=None: (_FakeCreds(fail=True), "p"))
    auth = agent_mod.GoogleAuth(GOOGLE_API_URL)

    assert "Authorization" not in _apply(auth, GOOGLE_API_URL).headers


def test_adc_resolution_is_cached(monkeypatch) -> None:
    calls = []

    def fake_default(scopes=None):
        calls.append(scopes)
        return _FakeCreds(), "proj"

    monkeypatch.setattr(agent_mod.google.auth, "default", fake_default)
    auth = agent_mod.GoogleAuth(GOOGLE_API_URL)

    _apply(auth, GOOGLE_API_URL)
    _apply(auth, GOOGLE_API_URL)

    assert len(calls) == 1, "google.auth.default() should resolve once, not per request"


def test_adc_requests_the_cloud_platform_scope(monkeypatch) -> None:
    """Unscoped ADC 401s under Agent Identity; a service account hid this."""
    seen = {}

    def fake_default(scopes=None):
        seen["scopes"] = scopes
        return _FakeCreds(), "proj"

    monkeypatch.setattr(agent_mod.google.auth, "default", fake_default)
    _apply(agent_mod.GoogleAuth(GOOGLE_API_URL), GOOGLE_API_URL)

    assert seen["scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]


# --- Cloud Run: audience-bound ID token, cached until expiry ----------------


def test_cloud_run_uses_an_id_token(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_mod,
        "_fetch_id_token",
        lambda url: ("id-tok", datetime.now(timezone.utc) + timedelta(hours=1)),
    )
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    assert _apply(auth).headers["Authorization"] == "Bearer id-tok"


def test_cloud_run_token_is_reused_while_valid(monkeypatch) -> None:
    calls = []

    def fake(url):
        calls.append(url)
        return "tok", datetime.now(timezone.utc) + timedelta(hours=1)

    monkeypatch.setattr(agent_mod, "_fetch_id_token", fake)
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    _apply(auth)
    _apply(auth)
    assert len(calls) == 1


def test_cloud_run_token_is_reminted_near_expiry(monkeypatch) -> None:
    """The expiry regression: a pinned ID token 401s after about an hour."""
    minted = []

    def fake(url):
        token = f"tok-{len(minted) + 1}"
        minted.append(token)
        return token, datetime.now(timezone.utc) + timedelta(minutes=1)

    monkeypatch.setattr(agent_mod, "_fetch_id_token", fake)
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    assert _apply(auth).headers["Authorization"] == "Bearer tok-1"
    assert _apply(auth).headers["Authorization"] == "Bearer tok-2"


def test_cloud_run_naive_expiry_is_treated_as_utc(monkeypatch) -> None:
    """google.auth hands back naive UTC datetimes; comparing them would raise."""
    naive = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
    monkeypatch.setattr(agent_mod, "_fetch_id_token", lambda url: ("tok", naive))
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    assert _apply(auth).headers["Authorization"] == "Bearer tok"


def test_cloud_run_unknown_expiry_falls_back_to_an_assumed_ttl(monkeypatch) -> None:
    """Never cache forever: an unknown expiry is the original bug in disguise."""
    calls = []
    monkeypatch.setattr(
        agent_mod,
        "_fetch_id_token",
        lambda url: (calls.append(url), ("tok", None))[1],
    )
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    _apply(auth)
    _apply(auth)
    assert len(calls) == 1
    assert auth._expires_at <= datetime.now(timezone.utc) + agent_mod._ASSUMED_TOKEN_TTL


def test_cloud_run_request_is_unauthenticated_when_minting_fails(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_fetch_id_token", lambda url: None)
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    assert "Authorization" not in _apply(auth).headers


def test_cloud_run_stale_token_is_kept_when_refresh_fails(monkeypatch) -> None:
    """A transient metadata-server blip should not strip a working credential."""
    state = {"first": True}

    def fake(url):
        if state["first"]:
            state["first"] = False
            return "tok-1", datetime.now(timezone.utc) + timedelta(minutes=1)
        return None

    monkeypatch.setattr(agent_mod, "_fetch_id_token", fake)
    auth = agent_mod.GoogleAuth(CLOUD_RUN_URL)

    assert _apply(auth).headers["Authorization"] == "Bearer tok-1"
    assert _apply(auth).headers["Authorization"] == "Bearer tok-1"


# --- delegated ID token (Agent Identity -> Cloud Run) -----------------------


class _FakeIamClient:
    """Stands in for IAMCredentialsClient, recording the token request."""

    def __init__(self, token="delegated-tok", fail=False):
        self.token, self.fail, self.calls = token, fail, []

    def generate_id_token(self, *, name, audience, include_email):
        self.calls.append((name, audience, include_email))
        if self.fail:
            raise RuntimeError("iam refused")
        return type("R", (), {"token": self.token})()


def _patch_iam(monkeypatch, client):
    from google.cloud import iam_credentials_v1

    monkeypatch.setattr(
        iam_credentials_v1, "IAMCredentialsClient", lambda credentials=None: client
    )


def test_delegate_is_skipped_when_no_service_account_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_DELEGATE_SERVICE_ACCOUNT", None)

    assert agent_mod._mint_delegated_id_token("https://svc.run.app") is None


def test_delegate_mints_an_id_token_for_the_target_audience(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_DELEGATE_SERVICE_ACCOUNT", "d@p.iam.gserviceaccount.com")
    monkeypatch.setattr(agent_mod, "_adc", lambda: _FakeCreds())
    client = _FakeIamClient()
    _patch_iam(monkeypatch, client)

    assert agent_mod._mint_delegated_id_token("https://svc.run.app") == "delegated-tok"
    name, audience, include_email = client.calls[0]
    assert name == "projects/-/serviceAccounts/d@p.iam.gserviceaccount.com"
    assert audience == "https://svc.run.app"
    assert include_email is True


def test_delegate_uses_the_agents_own_credential_to_authorize_the_mint(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_DELEGATE_SERVICE_ACCOUNT", "d@p.iam.gserviceaccount.com")
    creds = _FakeCreds()
    monkeypatch.setattr(agent_mod, "_adc", lambda: creds)
    seen = {}

    from google.cloud import iam_credentials_v1

    def _factory(credentials=None):
        # The client must be built on the bound credential -- it is what
        # negotiates mTLS. Letting it fall back to its own ADC drops the binding.
        seen["credentials"] = credentials
        return _FakeIamClient()

    monkeypatch.setattr(iam_credentials_v1, "IAMCredentialsClient", _factory)
    agent_mod._mint_delegated_id_token("https://svc.run.app")

    assert seen["credentials"] is creds


def test_delegate_returns_none_when_iam_refuses(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_DELEGATE_SERVICE_ACCOUNT", "d@p.iam.gserviceaccount.com")
    monkeypatch.setattr(agent_mod, "_adc", lambda: _FakeCreds())
    _patch_iam(monkeypatch, _FakeIamClient(fail=True))

    assert agent_mod._mint_delegated_id_token("https://svc.run.app") is None


def test_delegate_returns_none_without_credentials(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_DELEGATE_SERVICE_ACCOUNT", "d@p.iam.gserviceaccount.com")
    monkeypatch.setattr(agent_mod, "_adc", lambda: None)

    assert agent_mod._mint_delegated_id_token("https://svc.run.app") is None


def test_fetch_id_token_prefers_the_delegate_over_the_metadata_server(monkeypatch) -> None:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    monkeypatch.setattr(agent_mod, "_mint_delegated_id_token", lambda aud: _jwt(exp))

    def _fail(*a, **k):
        raise AssertionError("metadata server must not be consulted")

    monkeypatch.setattr(agent_mod.httpx, "get", _fail)
    token, expiry = agent_mod._fetch_id_token(CLOUD_RUN_URL)

    assert token == _jwt(exp)
    assert expiry is not None


def test_fetch_id_token_falls_back_when_no_delegate_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(agent_mod, "_mint_delegated_id_token", lambda aud: None)
    exp = datetime.now(timezone.utc) + timedelta(hours=1)

    class _Resp:
        status_code, text = 200, _jwt(exp)

    monkeypatch.setattr(agent_mod.httpx, "get", lambda *a, **k: _Resp())
    token, _ = agent_mod._fetch_id_token(CLOUD_RUN_URL)

    assert token == _jwt(exp)
