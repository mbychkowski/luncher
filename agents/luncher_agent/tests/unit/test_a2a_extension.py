"""Tests for A2UI extension activation (app.app_utils.a2a).

Advertising A2UI on the card is half the handshake: without per-request
activation the SDK sends no ``X-A2A-Extensions`` echo and the client discards
the data parts.
"""

import pytest

from app.app_utils import a2a as a2a_mod


class _FakeCallContext:
    def __init__(self, requested=()):
        self.requested_extensions = set(requested)
        self.activated_extensions = set()


class _FakeRequestContext:
    """Mirrors the seam a2a's RequestContext exposes to an executor."""

    def __init__(self, requested=()):
        self._call_context = _FakeCallContext(requested)

    @property
    def requested_extensions(self):
        return self._call_context.requested_extensions

    def add_activated_extension(self, uri):
        self._call_context.activated_extensions.add(uri)

    @property
    def activated(self):
        return self._call_context.activated_extensions


def _a2ui_uri() -> str:
    from a2ui.a2a.extension import get_a2ui_extension_uri

    return get_a2ui_extension_uri(a2a_mod._A2UI_VERSION)


@pytest.fixture
def card():
    """An agent card advertising A2UI, as attach_a2a_routes builds."""
    from a2a.types import AgentCard

    caps = a2a_mod._default_capabilities()
    return AgentCard(
        name="luncher_agent",
        description="test",
        url="https://example.invalid/a2a/luncher_agent",
        version="0.1.0",
        capabilities=caps,
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[],
    )


def test_card_advertises_the_a2ui_extension() -> None:
    uris = [e.uri for e in a2a_mod._default_capabilities().extensions]

    assert _a2ui_uri() in uris


def test_a2ui_is_activated_when_the_client_requests_it(card) -> None:
    from a2ui.a2a.extension import try_activate_a2ui_extension

    ctx = _FakeRequestContext(requested=[_a2ui_uri()])
    try_activate_a2ui_extension(ctx, card)

    # Activation is what makes the SDK echo X-A2A-Extensions; without it the
    # client discards the A2UI parts and renders an empty reply.
    assert ctx.activated == {_a2ui_uri()}


def test_nothing_is_activated_for_a_client_that_asks_for_nothing(card) -> None:
    from a2ui.a2a.extension import try_activate_a2ui_extension

    ctx = _FakeRequestContext(requested=[])
    try_activate_a2ui_extension(ctx, card)

    assert ctx.activated == set()


def test_unrelated_requested_extensions_do_not_activate_a2ui(card) -> None:
    from a2ui.a2a.extension import try_activate_a2ui_extension

    ctx = _FakeRequestContext(requested=["https://example.invalid/some-other-ext"])
    try_activate_a2ui_extension(ctx, card)

    assert ctx.activated == set()


def test_executor_activates_a2ui_before_delegating(card, monkeypatch) -> None:
    """The wiring, not just the helper: the executor must call activation."""
    import asyncio

    from google.adk.a2a.executor import a2a_agent_executor as adk_exec

    delegated = []

    async def _fake_execute(self, context, event_queue):
        # Ordering matters: activation has to happen before the response is
        # produced, or the header is already on its way out.
        delegated.append(set(context.activated))

    monkeypatch.setattr(adk_exec.A2aAgentExecutor, "execute", _fake_execute)

    executor = a2a_mod._build_executor(runner=object(), agent_card=card)
    ctx = _FakeRequestContext(requested=[_a2ui_uri()])
    asyncio.run(executor.execute(ctx, event_queue=object()))

    assert delegated == [{_a2ui_uri()}]
