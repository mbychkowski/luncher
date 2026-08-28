# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import functools
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import vertexai

import anyio.to_thread
import httpx
import google.auth
from google.auth.transport.requests import Request

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.apps.app import App
from google.adk.models.google_llm import Gemini
from google.genai.types import (
    HttpRetryOptions,
    ThinkingConfig,
    ThinkingLevel,
)

from app.app_utils.genai_transport import GenaiApiTransport
from app.a2ui_builder import ROLE_DESCRIPTION as SYNTHESIZER_INSTRUCTION
from app.a2ui_builder import (
    A2uiHistoryPlugin,
    a2ui_emit_callback,
    propose_lunch_tool,
)

# Defaults to Python's own unset level. LOG_LEVEL=INFO adds the per-event A2A
# author lines, which show whether a turn was filtered. An unknown level raises
# here rather than quietly falling back.
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING").upper())
logger = logging.getLogger(__name__)

# Load environment variables
# override=True: a stale shell export must not beat .env.
load_dotenv(override=True)

# Gemini Enterprise Agent Platform (GEAP) & GCP Project configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_LOCATION = os.getenv("GOOGLE_GENAI_LOCATION", "global")
# Pinned version. Override via GOOGLE_GENAI_MODEL. Only served from the `global`
# endpoint -- regional locations return 404 for it.
MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-3.6-flash")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

logger.info("Using Gemini model '%s' in location '%s'", MODEL, MODEL_LOCATION)

vertexai.init(project=PROJECT_ID, location=LOCATION)


# Re-mint a token this long before it actually expires, so a request that is
# in flight when the clock runs out still carries a valid credential.
_TOKEN_REFRESH_SKEW = timedelta(minutes=5)

# Assumed lifetime when the source does not tell us when the token expires.
# Deliberately shorter than the ~1h Google issues, since guessing too long
# reintroduces the expiry bug while guessing short only costs a mint.
_ASSUMED_TOKEN_TTL = timedelta(minutes=30)


def _jwt_expiry(token: str) -> datetime | None:
    """Reads the ``exp`` claim out of a JWT without verifying it.

    Only used to decide when to re-mint our own token; the receiving service
    does the actual verification.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception:
        return None


# The peer's host decides how the call is authenticated.
_AIPLATFORM_HOST_SUFFIX = "aiplatform.googleapis.com"
_CLOUD_RUN_HOST_SUFFIX = "run.app"


# Must be explicit: a service account carries this scope implicitly, an Agent
# Identity credential does not, and unscoped ADC is 401'd (not 403).
_ADC_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


@functools.cache
def _adc() -> "google.auth.credentials.Credentials | None":
    """Application Default Credentials for this runtime, resolved once.

    Under Agent Identity there is no service account: ADC resolves to the
    agent's own principal, and the credential object is the only thing that
    knows how to present it. Anything that reads ``creds.token`` off it and
    builds its own header is reaching around that and gets a 401.
    """
    try:
        creds, _ = google.auth.default(scopes=_ADC_SCOPES)
        logger.info(
            "ADC resolved to %s (scopes=%s)",
            type(creds).__name__,
            getattr(creds, "scopes", None),
        )
        return creds
    except Exception as e:
        logger.warning("Could not resolve Application Default Credentials: %s", e)
        return None


def _apply_adc(url: str, headers: dict[str, str]) -> bool:
    """Applies ADC to ``headers``, refreshing the credential if it has expired.

    ``before_request`` is what makes this work where the previous
    ``refresh()``-then-read-``.token`` did not: the credential applies itself,
    so a type that does not surface a plain bearer token still authenticates,
    and expiry is the library's problem rather than ours.
    """
    creds = _adc()
    if creds is None:
        return False
    try:
        creds.before_request(Request(), "POST", url, headers)
        return True
    except Exception as e:
        logger.warning("Could not apply ADC to %s: %s", url, e)
        return False


# Reaches Cloud Run peers under Agent Identity, which cannot mint an
# audience-bound ID token as itself. Unset, the metadata server path below is used.
_DELEGATE_SERVICE_ACCOUNT = os.getenv("CLOUD_RUN_DELEGATE_SERVICE_ACCOUNT")

def _mint_delegated_id_token(audience: str) -> str | None:
    """Mints an ID token for ``audience`` as the delegate service account.

    Uses the generated client, not a hand-built POST: an Agent Identity
    credential is certificate-bound and must go over mTLS, so a plain
    ``Authorization`` header to ``iamcredentials.googleapis.com`` is 401'd.
    """
    if not _DELEGATE_SERVICE_ACCOUNT:
        return None
    creds = _adc()
    if creds is None:
        return None
    try:
        from google.cloud import iam_credentials_v1

        client = iam_credentials_v1.IAMCredentialsClient(credentials=creds)
        response = client.generate_id_token(
            name=f"projects/-/serviceAccounts/{_DELEGATE_SERVICE_ACCOUNT}",
            audience=audience,
            include_email=True,
        )
        # Logged on success too: a silent fall-through to the metadata server
        # only surfaces as a later 401, and the path taken is what separates them.
        logger.info(
            "Minted a delegated ID token as %s for %s", _DELEGATE_SERVICE_ACCOUNT, audience
        )
        return response.token
    except Exception as e:
        logger.warning(
            "Could not mint a delegated ID token as %s for %s: %s",
            _DELEGATE_SERVICE_ACCOUNT,
            audience,
            e,
        )
    return None


def _fetch_id_token(url: str) -> tuple[str, datetime | None] | None:
    """Mints an identity token for a Cloud Run ``url``.

    Cloud Run authenticates callers with an ID token bound to the service as
    audience, which is a different credential from the access token Google APIs
    take -- hence a separate path rather than :func:`_apply_adc`.
    """
    target_audience = url.split("/a2a")[0].split("/.well-known")[0]

    # Delegate first when one is configured: under Agent Identity it is the only
    # path that yields a usable token, and where it is not configured it is a
    # no-op that costs nothing.
    if token := _mint_delegated_id_token(target_audience):
        return token, _jwt_expiry(token)

    # Metadata server next: it is present on both Cloud Run and Agent Runtime.
    try:
        meta_url = f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={target_audience}"
        meta_resp = httpx.get(meta_url, headers={"Metadata-Flavor": "Google"}, timeout=5.0)
        if meta_resp.status_code == 200 and meta_resp.text:
            token = meta_resp.text.strip()
            return token, _jwt_expiry(token)
        logger.warning(
            "Metadata server returned %s for an ID token for %s: %s",
            meta_resp.status_code,
            target_audience,
            meta_resp.text[:200],
        )
    except Exception as e:
        logger.warning("Metadata server ID token request failed for %s: %s", target_audience, e)

    try:
        from google.oauth2 import id_token

        token = id_token.fetch_id_token(Request(), target_audience)
        return token, _jwt_expiry(token)
    except Exception as e:
        logger.warning("Could not mint an ID token for %s: %s", target_audience, e)
    return None


class GoogleAuth(httpx.Auth):
    """Authenticates each outbound request, refreshing credentials as needed.

    Credentials are applied per request, never fetched once and pinned to the
    client: tokens last about an hour while a warm Agent Runtime instance holds
    its ``RemoteA2aAgent`` clients far longer, so a pinned header starts
    returning 401 after the first hour of uptime.

    Google APIs get ADC applied by the credential itself; Cloud Run gets an
    audience-bound ID token, which is a separate credential ADC does not
    provide, so that path still caches and re-mints on expiry.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._is_cloud_run = _CLOUD_RUN_HOST_SUFFIX in url
        self._token: str | None = None
        self._expires_at = datetime.min.replace(tzinfo=timezone.utc)

    def _authenticate(self, headers: dict[str, str]) -> None:
        if not self._is_cloud_run:
            _apply_adc(self._url, headers)
            return

        now = datetime.now(timezone.utc)
        if self._token is None or now >= self._expires_at - _TOKEN_REFRESH_SKEW:
            if minted := _fetch_id_token(self._url):
                self._token, expiry = minted
                # google.auth may hand back a naive UTC datetime.
                if expiry is not None and expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                self._expires_at = expiry or now + _ASSUMED_TOKEN_TTL
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

    def sync_auth_flow(self, request: httpx.Request):
        self._authenticate(request.headers)
        yield request

    async def async_auth_flow(self, request: httpx.Request):
        # Credential work does blocking I/O (metadata server, token endpoint).
        await anyio.to_thread.run_sync(self._authenticate, request.headers)
        yield request


def discover_sub_agent(
    agent_name: str,
    default_local_url: str,
    description: str,
) -> RemoteA2aAgent:
    """Instantiates a RemoteA2aAgent using direct agent card URLs.

    Checks environment variable {AGENT_NAME}_URL (e.g. STRATEGY_AGENT_URL),
    falling back to default_local_url for local offline development.
    """
    env_url_var = f"{agent_name.upper()}_URL"
    agent_url = os.getenv(env_url_var, default_local_url)
    # The variable name is derived from the agent name, and a mismatch is not an
    # error -- it silently falls back to localhost -- so record which source won.
    logger.info(
        "Connecting '%s' via %s: %s",
        agent_name,
        env_url_var if os.getenv(env_url_var) else f"default ({env_url_var} unset)",
        agent_url,
    )

    if _AIPLATFORM_HOST_SUFFIX in agent_url:
        # An Agent Runtime peer. Its endpoint rejects a bearer header built from
        # ADC under Agent Identity, so the request goes through the genai
        # client's transport instead -- see app_utils.genai_transport.
        client = httpx.AsyncClient(
            transport=GenaiApiTransport.from_url(agent_url), timeout=120.0
        )
        logger.info("  '%s' authenticates via the genai client transport", agent_name)
    else:
        # Cloud Run wants an audience-bound ID token; local dev URLs want
        # nothing, and skipping GoogleAuth there avoids a pointless metadata
        # lookup on every request.
        needs_auth = (
            _CLOUD_RUN_HOST_SUFFIX in agent_url or "googleapis.com" in agent_url
        )
        client = httpx.AsyncClient(
            auth=GoogleAuth(agent_url) if needs_auth else None, timeout=120.0
        )
        if not needs_auth:
            strategy = "no credential (local dev)"
        elif _CLOUD_RUN_HOST_SUFFIX in agent_url:
            strategy = (
                f"an ID token minted as {_DELEGATE_SERVICE_ACCOUNT}"
                if _DELEGATE_SERVICE_ACCOUNT
                else "an ID token from the metadata server"
            )
        else:
            strategy = "ADC applied by the credential"
        logger.info("  '%s' authenticates via %s", agent_name, strategy)

    return RemoteA2aAgent(
        name=agent_name,
        description=description,
        agent_card=agent_url,
        httpx_client=client,
        timeout=120.0,
    )


# Discover sub-agents (Strategy Agent and Scheduling Agent)
strategy_agent = discover_sub_agent(
    agent_name="strategy_agent",
    default_local_url="http://localhost:8081/a2a/app/.well-known/agent-card.json",
    description=(
        "Analyzes GeniCo corporate strategy and product initiative roadmaps (e.g. OmniChef, "
        "VisionSphere, PowerGrid Home). Consult this agent for strategic context and launch schedules."
    ),
)

scheduling_agent = discover_sub_agent(
    agent_name="scheduling_agent",
    default_local_url="http://localhost:8082/a2a/app/.well-known/agent-card.json",
    description=(
        "Helps coordinate meeting times and availability across team members interactively."
    ),
)

default_retry_policy = HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503],
)

# Stage 1 (Parallel): Gather corporate strategy and scheduling options concurrently
parallel_sub_agents = ParallelAgent(
    name="parallel_info_gatherer",
    description="Gathers corporate strategy context and team availability concurrently.",
    sub_agents=[strategy_agent, scheduling_agent],
)

# Stage 2: synthesize into a lunch proposal, rendered as A2UI v0.8. The model
# calls `propose_lunch` with domain data and Python builds the surface
# (app/a2ui_builder.py), so the tree is valid by construction.
synthesizer_agent = Agent(
    model=Gemini(
        model=MODEL,
        # Not MINIMAL: this agent reconciles sub-agent outputs and carries
        # the roster and per-slot free counts across verbatim. At MINIMAL it
        # intermittently rewrites the attendee list rather than copying it.
        thinking_config=ThinkingConfig(thinking_level=ThinkingLevel.LOW),
        retry_options=default_retry_policy,
        client_kwargs={"location": MODEL_LOCATION},
    ),
    name="lunch_synthesizer",
    description="Synthesizes corporate strategy objectives and scheduling options into a team lunch proposal.",
    instruction=SYNTHESIZER_INSTRUCTION,
    tools=[propose_lunch_tool],
    after_model_callback=a2ui_emit_callback,
)

# Root Orchestrator: 2-stage workflow executing parallel information gathering then synthesis
luncher_agent = SequentialAgent(
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    sub_agents=[parallel_sub_agents, synthesizer_agent],
)

root_agent = luncher_agent

app = App(
    name="luncher_agent",
    root_agent=root_agent,
    # App-wide, not synthesizer-only: every agent in the app is handed the same
    # conversation history, so sub-agents would otherwise carry the surface too.
    plugins=[A2uiHistoryPlugin()],
)


