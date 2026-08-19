import json
import os

import pytest
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai.types import Content, Part

from a2ui.a2a.parts import is_a2ui_part
from google.genai.types import Part as GenAIPart

from app.a2ui import (
    A2UI_FORMAT,
    EXAMPLES_PATH,
    a2ui_gen_ai_part_converter,
    find_binding_problems,
)
from app.app_utils import a2a as a2a_utils

A2UI_EXTENSION_URI = "https://a2ui.org/a2a-extension/a2ui/v0.8"
A2UI_MIME_TYPE = "application/json+a2ui"
STANDARD_CATALOG_ID = (
    "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
)


@pytest.fixture(scope="module")
def example_payload() -> list:
    with open(os.path.join(EXAMPLES_PATH, "lunch_proposal.json")) as handle:
        return json.load(handle)



def _wrap(payload: list) -> str:
    return "Here is your lunch proposal.<a2ui-json>" + json.dumps(payload) + "</a2ui-json>"


# --- Agent card ------------------------------------------------------------


def test_card_advertises_a2ui_extension() -> None:
    """Gemini Enterprise only renders A2UI for agents declaring this extension."""
    capabilities = a2a_utils._default_capabilities()

    extensions = {ext.uri: ext for ext in capabilities.extensions}
    assert A2UI_EXTENSION_URI in extensions
    assert extensions[A2UI_EXTENSION_URI].params["supportedCatalogIds"] == [
        STANDARD_CATALOG_ID
    ]


def test_card_retains_adk_executor_extension() -> None:
    capabilities = a2a_utils._default_capabilities()

    assert any(
        ext.uri == a2a_utils._ADK_AGENT_EXECUTOR_EXTENSION_URI
        for ext in capabilities.extensions
    )


def test_card_advertises_streaming() -> None:
    """The ADK A2A route serves message/stream on every target we deploy to.

    Verified against a live Agent Runtime deployment: ``message/stream`` returns
    200 ``text/event-stream`` through the reasoning-engine ``/api`` passthrough.
    """
    assert a2a_utils._default_capabilities().streaming is True


def test_sdk_gates_streaming_on_the_card() -> None:
    """The card cannot overstate the server: the a2a SDK enforces the claim.

    Guards the assumption behind hardcoding ``streaming=True`` — that a caller
    overriding ``capabilities`` gets a server matching the card for free, with
    no enforcement of our own.
    """
    card = AgentCard(
        name="probe",
        description="probe",
        url="http://testserver/a2a",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[AgentSkill(id="s", name="s", description="d", tags=["t"])],
    )
    app = FastAPI()
    A2AFastAPIApplication(
        agent_card=card,
        http_handler=DefaultRequestHandler(
            agent_executor=None, task_store=InMemoryTaskStore()
        ),
    ).add_routes_to_app(app, rpc_url="/a2a")

    with TestClient(app) as client:
        response = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "message/stream",
                "params": {
                    "message": {
                        "role": "user",
                        "messageId": "m1",
                        "parts": [{"kind": "text", "text": "hi"}],
                    }
                },
            },
        )

    assert "error" in response.json()
    assert "streaming is not supported" in response.text.lower()


# --- Payload validation ----------------------------------------------------


def test_example_payload_validates(example_payload) -> None:
    A2UI_FORMAT.get_selected_catalog().validator.validate(example_payload)


def test_unknown_component_is_rejected() -> None:
    bad = [
        {
            "surfaceUpdate": {
                "surfaceId": "lunch-proposal",
                "components": [{"id": "x", "component": {"Table": {"rows": []}}}],
            }
        }
    ]
    with pytest.raises(Exception):
        A2UI_FORMAT.get_selected_catalog().validator.validate(bad)



# --- A2A boundary conversion -----------------------------------------------



def test_a2a_converter_produces_data_parts(example_payload) -> None:
    """A2A consumers (Gemini Enterprise) need data parts, not tagged text."""
    parts = a2ui_gen_ai_part_converter(GenAIPart(text=_wrap(example_payload)))

    assert isinstance(parts, list)
    data_parts = [p for p in parts if is_a2ui_part(p)]
    assert len(data_parts) == len(example_payload)
    for part in data_parts:
        assert part.root.metadata["mimeType"] == A2UI_MIME_TYPE


def test_a2a_converter_passes_through_plain_text() -> None:
    """Non-A2UI parts fall through to ADK's default conversion, unchanged."""
    result = a2ui_gen_ai_part_converter(GenAIPart(text="Just prose."))

    assert [part.root.text for part in result] == ["Just prose."]


def test_a2a_converter_keeps_the_surrounding_prose(example_payload) -> None:
    """The summary travels with the surface; A2A consumers need both."""
    parts = a2ui_gen_ai_part_converter(GenAIPart(text=_wrap(example_payload)))

    texts = [p.root.text for p in parts if not is_a2ui_part(p)]
    assert texts == ["Here is your lunch proposal."]


def test_a2a_converter_falls_back_when_the_payload_is_unparseable() -> None:
    """Never hand an A2A consumer an empty message: no parts means no response."""
    parts = a2ui_gen_ai_part_converter(
        GenAIPart(text="Broken.<a2ui-json>{not json</a2ui-json>")
    )

    assert [p.root.text for p in parts] == ["The lunch proposal could not be rendered."]





# --- Data binding ----------------------------------------------------------


def _surface(components: list) -> list:
    return [{"surfaceUpdate": {"surfaceId": "s", "components": components}}]


def _slot_picker(selections: dict) -> dict:
    return {
        "id": "slot-picker",
        "component": {
            "MultipleChoice": {
                "selections": selections,
                "options": [
                    {"label": {"literalString": "Tue"}, "value": "2026-08-12T12:00"},
                    {"label": {"literalString": "Wed"}, "value": "2026-08-13T12:30"},
                ],
                "maxAllowedSelections": 1,
            }
        },
    }


def _book_button(context_value: dict) -> dict:
    return {
        "id": "book-button",
        "component": {
            "Button": {
                "child": "book-button-text",
                "primary": True,
                "action": {
                    "name": "book_lunch",
                    "context": [{"key": "selectedSlot", "value": context_value}],
                },
            }
        },
    }


def test_example_payload_has_no_binding_problems(example_payload) -> None:
    assert find_binding_problems(example_payload) == []


def test_literal_selections_are_rejected() -> None:
    """A literal leaves the user's choice with nowhere to be written."""
    payload = _surface([_slot_picker({"literalArray": ["2026-08-12T12:00"]})])

    problems = find_binding_problems(payload)

    assert len(problems) == 1
    assert "slot-picker" in problems[0] and "literalArray" in problems[0]


def test_action_context_copying_a_selectable_value_is_rejected() -> None:
    """The exact defect the model produced: the button ignores the user's pick."""
    payload = _surface(
        [
            _slot_picker({"path": "/selectedSlots"}),
            _book_button({"literalString": "2026-08-12T12:00"}),
        ]
    )

    problems = find_binding_problems(payload)

    assert len(problems) == 1
    assert "book-button" in problems[0]


def test_bound_selections_and_action_are_accepted() -> None:
    payload = _surface(
        [
            _slot_picker({"path": "/selectedSlots"}),
            _book_button({"path": "/selectedSlots"}),
        ]
    )

    assert find_binding_problems(payload) == []


def test_constant_action_metadata_is_allowed() -> None:
    """Literals are fine when they are genuinely fixed, not user-selectable."""
    payload = _surface(
        [
            _slot_picker({"path": "/selectedSlots"}),
            _book_button({"literalString": "lunch-proposal"}),
        ]
    )

    assert find_binding_problems(payload) == []


def test_all_interactive_components_are_covered() -> None:
    payload = _surface(
        [
            {"id": "c1", "component": {"CheckBox": {"value": {"literalBoolean": True}}}},
            {"id": "c2", "component": {"TextField": {"text": {"literalString": "hi"}}}},
            {"id": "c3", "component": {"Slider": {"value": {"literalNumber": 3}}}},
            {"id": "c4", "component": {"DateTimeInput": {"value": {"literalString": "x"}}}},
        ]
    )

    assert len(find_binding_problems(payload)) == 4


