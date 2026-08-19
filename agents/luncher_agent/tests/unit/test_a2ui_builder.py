import asyncio
import json
from unittest.mock import MagicMock

import pytest
from google.genai.types import Content, Part

from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from app.a2ui_builder import (
    A2uiHistoryPlugin,
    PAYLOAD_STATE_KEY,
    a2ui_emit_callback,
    build_lunch_surface,
    propose_lunch,
)
from app.a2ui import A2UI_FORMAT, find_binding_problems

SLOTS = [
    {"label": "Tue 12 Aug, 12:00-13:00", "value": "2026-08-12T12:00"},
    {"label": "Wed 13 Aug, 12:30-13:30", "value": "2026-08-13T12:30"},
]
MENU = [
    {"name": "Mezze platter", "dietary_note": "Vegetarian, dairy-free option"},
    {"name": "Quinoa bowls", "dietary_note": "Gluten-free"},
]


def _build(**overrides) -> list:
    kwargs = dict(
        title="OmniChef Launch Alignment Lunch",
        rationale="Aligns leads ahead of the Q4 milestone review.",
        attendees=["Liam", "Diego", "Maya"],
        time_slots=SLOTS,
        recommended_slot="2026-08-12T12:00",
        menu_items=MENU,
    )
    kwargs.update(overrides)
    return build_lunch_surface(**kwargs)


# --- Structural guarantees -------------------------------------------------


def test_payload_validates_against_catalog() -> None:
    A2UI_FORMAT.get_selected_catalog().validator.validate(_build())


def test_payload_has_no_binding_problems() -> None:
    """The defect class the prompt path could only ask for, now impossible."""
    assert find_binding_problems(_build()) == []


def test_emits_the_three_message_kinds() -> None:
    assert [next(iter(m)) for m in _build()] == [
        "beginRendering",
        "surfaceUpdate",
        "dataModelUpdate",
    ]


def test_styles_and_alignment_are_always_set() -> None:
    payload = _build()
    styles = payload[0]["beginRendering"]["styles"]
    assert styles["primaryColor"] and styles["font"]

    containers = [
        props
        for component in payload[1]["surfaceUpdate"]["components"]
        for name, props in component["component"].items()
        if name in ("Column", "List")
    ]
    assert containers and all(c["alignment"] == "start" for c in containers)


def test_slot_options_follow_the_given_slots() -> None:
    payload = _build()
    picker = next(
        props
        for component in payload[1]["surfaceUpdate"]["components"]
        for name, props in component["component"].items()
        if name == "MultipleChoice"
    )
    assert [o["value"] for o in picker["options"]] == [s["value"] for s in SLOTS]
    assert picker["selections"] == {"path": "/selectedSlots"}


# --- Argument validation ---------------------------------------------------


def test_recommended_slot_must_be_offered() -> None:
    with pytest.raises(ValueError, match="not one of the offered slots"):
        _build(recommended_slot="2026-12-25T12:00")


def test_at_least_one_slot_required() -> None:
    with pytest.raises(ValueError, match="at least one time slot"):
        _build(time_slots=[])


def test_tool_returns_error_text_instead_of_raising() -> None:
    """A bad argument must come back to the model as correctable text."""
    ctx = MagicMock()
    ctx.state = {}

    result = propose_lunch(
        title="t",
        rationale="r",
        attendees=["a"],
        slot_labels=[s["label"] for s in SLOTS],
        slot_values=[s["value"] for s in SLOTS],
        slot_absentees=["" for _ in SLOTS],
        recommended_slot="nope",
        menu_names=[m["name"] for m in MENU],
        menu_notes=[m["dietary_note"] for m in MENU],
        tool_context=ctx,
    )

    assert "Could not render" in result
    assert PAYLOAD_STATE_KEY not in ctx.state


def test_tool_stores_payload_in_state() -> None:
    ctx = MagicMock()
    ctx.state = {}

    result = propose_lunch(
        title="t",
        rationale="r",
        attendees=["a"],
        slot_labels=[s["label"] for s in SLOTS],
        slot_values=[s["value"] for s in SLOTS],
        slot_absentees=["" for _ in SLOTS],
        recommended_slot="2026-08-12T12:00",
        menu_names=[m["name"] for m in MENU],
        menu_notes=[m["dietary_note"] for m in MENU],
        tool_context=ctx,
    )

    assert "rendered" in result
    A2UI_FORMAT.get_selected_catalog().validator.validate(ctx.state[PAYLOAD_STATE_KEY])


# --- Attendee grounding ----------------------------------------------------

ROSTER_TEXT = (
    "Team availability: Liam, Diego, Dan, Maya, Aaliyah, Naomi, Jordan and Kai. "
    "Friday 12:00-13:00 is free for all 8."
)


def _ctx_with_roster(text: str | None) -> MagicMock:
    """A tool context whose session carries one scheduling_agent event."""
    ctx = MagicMock()
    ctx.state = {}
    ctx.invocation_id = "inv-1"
    events = []
    if text is not None:
        event = MagicMock()
        event.author = "scheduling_agent"
        event.invocation_id = "inv-1"
        event.content = Content(parts=[Part(text=text)])
        events.append(event)
    ctx.session.events = events
    return ctx


def _propose(ctx: MagicMock, attendees: list[str]) -> str:
    return propose_lunch(
        title="t",
        rationale="r",
        attendees=attendees,
        slot_labels=[s["label"] for s in SLOTS],
        slot_values=[s["value"] for s in SLOTS],
        slot_absentees=["" for _ in SLOTS],
        recommended_slot="2026-08-12T12:00",
        menu_names=[m["name"] for m in MENU],
        menu_notes=[m["dietary_note"] for m in MENU],
        tool_context=ctx,
    )


def test_attendees_from_the_roster_render() -> None:
    ctx = _ctx_with_roster(ROSTER_TEXT)

    assert "rendered" in _propose(ctx, ["Liam", "Diego", "Kai"])


def test_invented_attendees_are_refused() -> None:
    ctx = _ctx_with_roster(ROSTER_TEXT)

    result = _propose(ctx, ["Alex Mercer", "Sam Chen"])

    assert "Could not render" in result
    assert "Alex Mercer" in result and "Sam Chen" in result
    assert PAYLOAD_STATE_KEY not in ctx.state


def test_a_real_first_name_does_not_carry_an_invented_surname() -> None:
    """"Jordan" is on the roster; "Jordan Taylor" is not."""
    ctx = _ctx_with_roster(ROSTER_TEXT)

    result = _propose(ctx, ["Jordan Taylor"])

    assert "Could not render" in result
    assert "Jordan Taylor" in result


def test_attendees_unchecked_when_the_scheduling_agent_said_nothing() -> None:
    """With no roster to judge against, the check cannot fire."""
    ctx = _ctx_with_roster(None)

    assert "rendered" in _propose(ctx, ["Whoever Nobody"])


def test_roster_from_another_invocation_is_ignored() -> None:
    ctx = _ctx_with_roster(ROSTER_TEXT)
    ctx.session.events[0].invocation_id = "inv-0"

    assert "rendered" in _propose(ctx, ["Whoever Nobody"])


# --- Who can't make it ----------------------------------------------------


def _absences(payload: list) -> list[dict]:
    """The rendered slot/who pairs, in order."""
    data = payload[2]["dataModelUpdate"]["contents"]
    entry = next(c for c in data if c["key"] == "slotAbsences")
    return [
        {p["key"]: p["valueString"] for p in row["valueMap"]}
        for row in entry["valueMap"]
    ]


def test_absentees_render_one_row_per_slot() -> None:
    payload = _build(
        time_slots=[
            {**SLOTS[0], "absent": ""},
            {**SLOTS[1], "absent": "Maya, Kai"},
        ]
    )

    assert _absences(payload) == [
        {"slot": SLOTS[0]["label"], "who": "Everyone can attend"},
        {"slot": SLOTS[1]["label"], "who": "Maya, Kai"},
    ]


def test_a_slot_with_no_absentee_still_gets_a_row() -> None:
    """Rows line up with the picker, so a full-attendance slot is not skipped."""
    payload = _build()

    assert len(_absences(payload)) == len(SLOTS)


def test_absentees_must_match_the_slot_count() -> None:
    ctx = _ctx_with_roster(ROSTER_TEXT)

    result = propose_lunch(
        title="t",
        rationale="r",
        attendees=["Liam"],
        slot_labels=[s["label"] for s in SLOTS],
        slot_values=[s["value"] for s in SLOTS],
        slot_absentees=["Kai"],
        recommended_slot="2026-08-12T12:00",
        menu_names=[m["name"] for m in MENU],
        menu_notes=[m["dietary_note"] for m in MENU],
        tool_context=ctx,
    )

    assert "Could not render" in result
    assert "one entry per slot" in result


def test_invented_absentees_are_refused() -> None:
    """An absentee is a team member, held to the same roster as attendees."""
    ctx = _ctx_with_roster(ROSTER_LINE_TEXT)

    result = propose_lunch(
        title="t",
        rationale="r",
        attendees=FULL_TEAM,
        slot_labels=[s["label"] for s in SLOTS],
        slot_values=[s["value"] for s in SLOTS],
        slot_absentees=["", "Priya Patel and Kai"],
        recommended_slot="2026-08-12T12:00",
        menu_names=[m["name"] for m in MENU],
        menu_notes=[m["dietary_note"] for m in MENU],
        tool_context=ctx,
    )

    assert "Could not render" in result
    # Only the invented name is named; the real one it was listed beside is not.
    assert "not on the team: Priya Patel." in result


# --- Roster line ----------------------------------------------------------

FULL_TEAM = ["Liam", "Diego", "Dan", "Maya", "Aaliyah", "Naomi", "Jordan", "Kai"]
ROSTER_LINE_TEXT = (
    "Team (8): Liam, Diego, Dan, Maya, Aaliyah, Naomi, Jordan, Kai\n"
    "1. Friday, 12:00-13:00 - 8 of 8 free\n"
    "2. Tuesday, 13:00-14:00 - 7 of 8 free (Kai unavailable)"
)


def test_the_named_team_renders() -> None:
    ctx = _ctx_with_roster(ROSTER_LINE_TEXT)

    assert "rendered" in _propose(ctx, FULL_TEAM)


def test_a_truncated_roster_is_refused() -> None:
    """Real names, but only the four the shortlist happened to mention."""
    ctx = _ctx_with_roster(ROSTER_LINE_TEXT)

    result = _propose(ctx, ["Kai", "Maya", "Aaliyah", "Naomi"])

    assert "Could not render" in result
    assert "missing" in result and "Liam" in result
    assert PAYLOAD_STATE_KEY not in ctx.state


def test_placeholder_attendees_are_refused() -> None:
    ctx = _ctx_with_roster(ROSTER_LINE_TEXT)

    result = _propose(ctx, ["Kai", "Maya", "Team Member 3", "Team Member 4"])

    assert "Could not render" in result
    assert "Team Member 3" in result


def test_roster_line_survives_markdown_emphasis() -> None:
    ctx = _ctx_with_roster(
        "**Team (8):** Liam, Diego, Dan, Maya, Aaliyah, Naomi, Jordan and Kai"
    )

    assert "rendered" in _propose(ctx, FULL_TEAM)


def test_roster_line_survives_a_trailing_full_stop() -> None:
    ctx = _ctx_with_roster(
        "Team (8): Liam, Diego, Dan, Maya, Aaliyah, Naomi, Jordan, Kai."
    )

    assert "rendered" in _propose(ctx, FULL_TEAM)


def test_a_roster_line_whose_count_disagrees_is_not_trusted() -> None:
    """A miscounted line falls back to the invention-only check."""
    ctx = _ctx_with_roster("Team (8): Liam, Diego\n" + ROSTER_TEXT)

    assert "rendered" in _propose(ctx, ["Liam", "Diego"])


# --- Emission callback -----------------------------------------------------


def _response(text: str) -> LlmResponse:
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


def test_callback_appends_payload_as_its_own_part() -> None:
    response = _response("Here is your lunch proposal.")
    ctx = MagicMock()
    ctx.state = {PAYLOAD_STATE_KEY: _build()}

    result = a2ui_emit_callback(ctx, response)

    assert result is not None
    # The model's summary is left exactly as it was; the surface rides alongside it.
    assert result.content.parts[0].text == "Here is your lunch proposal."
    block = result.content.parts[-1].text
    assert block.startswith("<a2ui-json>")
    payload = json.loads(block.split("<a2ui-json>")[1].split("</a2ui-json>")[0])
    A2UI_FORMAT.get_selected_catalog().validator.validate(payload)
    # Consumed, so a later turn does not re-emit it.
    assert ctx.state[PAYLOAD_STATE_KEY] is None


def test_callback_preserves_the_models_other_parts() -> None:
    """Rebuilding the parts list would drop signatures and leak thought text.

    A thought part's text is the model's reasoning, not its answer -- concatenating
    it into the summary would show it to the user.
    """
    response = LlmResponse(
        content=Content(
            role="model",
            parts=[
                Part(text="Deciding on a slot...", thought=True),
                Part(text="Here is your lunch proposal.", thought_signature=b"sig"),
            ],
        )
    )
    ctx = MagicMock()
    ctx.state = {PAYLOAD_STATE_KEY: _build()}

    result = a2ui_emit_callback(ctx, response)

    assert [p.thought for p in result.content.parts[:2]] == [True, None]
    assert result.content.parts[1].thought_signature == b"sig"
    assert result.content.parts[-1].text.startswith("<a2ui-json>")


def _trim(*contents) -> list:
    """Runs the history plugin over a request and returns the surviving contents."""
    request = LlmRequest(contents=list(contents))
    asyncio.run(
        A2uiHistoryPlugin().before_model_callback(
            callback_context=MagicMock(), llm_request=request
        )
    )
    return request.contents


def _model_turn(*parts) -> Content:
    return Content(role="model", parts=list(parts))


def _block() -> str:
    return "<a2ui-json>" + json.dumps(_build()) + "</a2ui-json>"


def test_history_plugin_drops_the_surface_and_keeps_the_summary() -> None:
    """The client already rendered it; replaying it costs ~2k tokens a turn."""
    contents = _trim(
        _model_turn(Part(text="Here is your lunch proposal."), Part(text=_block()))
    )

    assert [p.text for p in contents[0].parts] == ["Here is your lunch proposal."]


def test_history_plugin_handles_a_block_inline_in_the_summary() -> None:
    """Older turns, and any model that inlines the tag, keep their prose."""
    contents = _trim(_model_turn(Part(text="Proposal ready." + _block())))

    assert [p.text for p in contents[0].parts] == ["Proposal ready."]


def test_history_plugin_drops_a_turn_that_was_only_a_surface() -> None:
    contents = _trim(
        Content(role="user", parts=[Part(text="Plan lunch.")]),
        _model_turn(Part(text=_block())),
    )

    assert [c.role for c in contents] == ["user"]


def test_history_plugin_leaves_ordinary_history_alone() -> None:
    original = [
        Content(role="user", parts=[Part(text="Plan lunch.")]),
        _model_turn(Part(text="Sure.")),
    ]

    assert _trim(*original) == original


def test_history_plugin_does_not_mutate_the_stored_content() -> None:
    """These may be the session's own objects -- trimming is for the request only."""
    stored = _model_turn(Part(text="Summary."), Part(text=_block()))

    _trim(stored)

    assert [bool(p.text and "<a2ui-json>" in p.text) for p in stored.parts] == [
        False,
        True,
    ]


def test_payload_state_key_is_invocation_scoped() -> None:
    """`temp:` keeps a rendered surface out of persisted session state."""
    from google.adk.sessions.state import State

    assert PAYLOAD_STATE_KEY.startswith(State.TEMP_PREFIX)


def test_callback_consumes_the_payload_on_an_empty_response() -> None:
    """A surface that could not be attached is spent, not held for a later turn.

    The model occasionally returns nothing after calling the tool. Keeping the
    payload would render this lunch proposal against whatever the user asks next.
    """
    ctx = MagicMock()
    ctx.state = {PAYLOAD_STATE_KEY: _build()}

    assert a2ui_emit_callback(ctx, LlmResponse(content=None)) is None
    assert ctx.state[PAYLOAD_STATE_KEY] is None


def test_callback_skips_the_tool_call_turn() -> None:
    """The turn that calls the tool has no summary yet -- nothing to append to."""
    response = LlmResponse(
        content=Content(
            role="model",
            parts=[Part(function_call={"name": "propose_lunch", "args": {}})],
        )
    )
    ctx = MagicMock()
    ctx.state = {PAYLOAD_STATE_KEY: _build()}

    assert a2ui_emit_callback(ctx, response) is None
    assert ctx.state[PAYLOAD_STATE_KEY] is not None


def test_callback_noop_without_payload() -> None:
    ctx = MagicMock()
    ctx.state = {}

    assert a2ui_emit_callback(ctx, _response("Just prose.")) is None


def test_tool_rejects_mismatched_pair_lengths() -> None:
    """Parallel lists must correspond one to one, or slots silently drop."""
    ctx = MagicMock()
    ctx.state = {}

    result = propose_lunch(
        title="t",
        rationale="r",
        attendees=["a"],
        slot_labels=["Tue", "Wed"],
        slot_values=["2026-08-12T12:00"],
        slot_absentees=["", ""],
        recommended_slot="2026-08-12T12:00",
        menu_names=["m"],
        menu_notes=["n"],
        tool_context=ctx,
    )

    assert "correspond one to one" in result
    assert PAYLOAD_STATE_KEY not in ctx.state
