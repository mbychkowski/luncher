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

"""Deterministic A2UI surface construction, driven by a tool call.

The model calls :func:`propose_lunch` with plain domain data and Python builds
the A2UI tree. The alternative -- having the model author the tree itself from a
~7k-token system prompt carrying the catalog schema and worked examples -- was
measured at 3.5x the prompt tokens, 5.6x the output tokens and 1.7x the latency
for an identical result, and was removed. Building it here:

* drops the synthesizer's system prompt from ~7,400 tokens to ~200, and removes
  a few thousand output tokens per turn (no JSON tree to generate);
* makes whole bug classes structurally impossible rather than prompt-enforced --
  literal-vs-path bindings, missing ``alignment``, missing ``styles``, invented
  components. Function-call arguments are schema-constrained by the model API.

The trade is that the surface shape is fixed: the model can no longer restructure
the layout per response. Determinism applies to *structure*, not content -- the
model can still pass a slot that isn't free or misread a dietary note, which is
what the eval suite in ``tests/eval`` exists to measure.
"""

from __future__ import annotations

import json
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools import FunctionTool, ToolContext
from google.genai.types import Part

from a2ui.schema.constants import A2UI_CLOSE_TAG, A2UI_OPEN_TAG


SURFACE_ID = "lunch-proposal"
PRIMARY_COLOR = "#8AB4F8"
FONT = "Google Sans"

# Session-state key holding the payload between the tool call and the final model turn
# that emits it. The ``temp:`` prefix keeps it out of persisted session state (ADK trims
# those deltas in BaseSessionService), which is where a rendered surface has no business
# accumulating.
PAYLOAD_STATE_KEY = "temp:a2ui_payload"

ROLE_DESCRIPTION = (
    "You are the central Luncher Synthesizer Agent. You receive context containing "
    "retrieved team food preferences from memory, strategic corporate priorities, and "
    "team schedule options.\n\n"
    "Synthesize them into a single lunch proposal and call the `propose_lunch` tool to "
    "render it. Frame the lunch around the strategic objective it serves, include every "
    "team member by name, carry across who cannot attend each slot exactly as the "
    "scheduling agent reported it, and make sure the menu respects every dietary "
    "preference and allergy you were given -- noting which restriction each dish "
    "accommodates.\n\n"
    "After calling the tool, reply with one short sentence summarising the proposal. "
    "Do not describe the UI and do not output JSON.\n\n"
    "BOOKING TURNS. When the turn carries a `book_lunch` action rather than a fresh "
    "request, the user has pressed the button on a proposal you already made. Do not "
    "call `propose_lunch` again. Reply with a confirmation of at most four bullets -- "
    "time slot, catering, attendees, booking id -- and nothing else. No strategy "
    "recap, no restatement of the objectives, no closing pleasantries. You are the "
    "only agent the user hears, so say each fact once."
)


def _text(component_id: str, *, path: str | None = None, literal: str | None = None,
          usage_hint: str | None = None) -> dict:
    value = {"path": path} if path is not None else {"literalString": literal or ""}
    props: dict = {"text": value}
    if usage_hint:
        props["usageHint"] = usage_hint
    return {"id": component_id, "component": {"Text": props}}


def build_lunch_surface(
    *,
    title: str,
    rationale: str,
    attendees: list[str],
    time_slots: list[dict],
    recommended_slot: str,
    menu_items: list[dict],
) -> list[dict]:
    """Builds the three A2UI v0.8 messages for a lunch proposal.

    ``time_slots`` items carry ``label``, ``value`` and an optional ``absent``
    naming who cannot attend that slot; ``menu_items`` carry ``name`` and
    ``dietary_note``. Every interactive binding is a data-model path by
    construction, so the payload cannot exhibit the literal-binding defect.
    """
    if not time_slots:
        raise ValueError("at least one time slot is required")

    # A slot nobody misses still gets a row, so the list lines up with the picker
    # rather than silently skipping entries.
    time_slots = [
        {**slot, "absent": slot.get("absent") or "Everyone can attend"}
        for slot in time_slots
    ]

    values = [slot["value"] for slot in time_slots]
    if recommended_slot not in values:
        raise ValueError(
            f"recommended_slot {recommended_slot!r} is not one of the offered slots {values!r}"
        )

    components = [
        {"id": "proposal-card", "component": {"Card": {"child": "proposal-column"}}},
        {
            "id": "proposal-column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [
                            "proposal-title",
                            "strategy-rationale",
                            "attendees-heading",
                            "attendees-text",
                            "slots-heading",
                            "slot-picker",
                            "absence-heading",
                            "absence-list",
                            "menu-heading",
                            "menu-list",
                            "book-button",
                        ]
                    },
                    "alignment": "start",
                }
            },
        },
        _text("proposal-title", path="/title", usage_hint="h1"),
        _text("strategy-rationale", path="/rationale", usage_hint="body"),
        _text("attendees-heading", literal="Included Team Members", usage_hint="h3"),
        _text("attendees-text", path="/attendees", usage_hint="body"),
        _text("slots-heading", literal="Proposed Time Slots", usage_hint="h3"),
        {
            "id": "slot-picker",
            "component": {
                "MultipleChoice": {
                    # Always a path binding: the user's choice must have somewhere to go.
                    "selections": {"path": "/selectedSlots"},
                    "options": [
                        {"label": {"literalString": slot["label"]}, "value": slot["value"]}
                        for slot in time_slots
                    ],
                    "maxAllowedSelections": 1,
                    "variant": "chips",
                }
            },
        },
        _text("absence-heading", literal="Who Can't Make It", usage_hint="h3"),
        {
            "id": "absence-list",
            "component": {
                "List": {
                    "direction": "vertical",
                    "children": {
                        "template": {
                            "componentId": "absence-item-template",
                            "dataBinding": "/slotAbsences",
                        }
                    },
                    "alignment": "start",
                }
            },
        },
        {
            "id": "absence-item-template",
            "component": {
                "Column": {
                    "children": {"explicitList": ["absence-item-slot", "absence-item-who"]},
                    "alignment": "start",
                }
            },
        },
        _text("absence-item-slot", path="/slot", usage_hint="h5"),
        _text("absence-item-who", path="/who", usage_hint="caption"),
        _text("menu-heading", literal="Catering Menu", usage_hint="h3"),
        {
            "id": "menu-list",
            "component": {
                "List": {
                    "direction": "vertical",
                    "children": {
                        "template": {
                            "componentId": "menu-item-template",
                            "dataBinding": "/menuItems",
                        }
                    },
                    "alignment": "start",
                }
            },
        },
        {
            "id": "menu-item-template",
            "component": {
                "Column": {
                    "children": {"explicitList": ["menu-item-name", "menu-item-note"]},
                    "alignment": "start",
                }
            },
        },
        _text("menu-item-name", path="/name", usage_hint="h5"),
        _text("menu-item-note", path="/dietaryNote", usage_hint="caption"),
        _text("book-button-text", literal="Book this lunch"),
        {
            "id": "book-button",
            "component": {
                "Button": {
                    "child": "book-button-text",
                    "primary": True,
                    "action": {
                        "name": "book_lunch",
                        # Reads live state, so the action follows the user's choice.
                        # The surface is stripped from history once rendered, so
                        # whatever the confirmation needs has to travel here.
                        "context": [
                            {"key": "selectedSlots", "value": {"path": "/selectedSlots"}},
                            {"key": "title", "value": {"path": "/title"}},
                            {"key": "menuItems", "value": {"path": "/menuItems"}},
                        ],
                    },
                }
            },
        },
    ]

    return [
        {
            "beginRendering": {
                "surfaceId": SURFACE_ID,
                "root": "proposal-card",
                "styles": {"primaryColor": PRIMARY_COLOR, "font": FONT},
            }
        },
        {"surfaceUpdate": {"surfaceId": SURFACE_ID, "components": components}},
        {
            "dataModelUpdate": {
                "surfaceId": SURFACE_ID,
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": title},
                    {"key": "rationale", "valueString": rationale},
                    {"key": "attendees", "valueString": ", ".join(attendees)},
                    {
                        "key": "selectedSlots",
                        "valueMap": [{"key": "0", "valueString": recommended_slot}],
                    },
                    {
                        "key": "slotAbsences",
                        "valueMap": [
                            {
                                "key": f"slot{index}",
                                "valueMap": [
                                    {"key": "slot", "valueString": slot["label"]},
                                    {"key": "who", "valueString": slot["absent"]},
                                ],
                            }
                            for index, slot in enumerate(time_slots, start=1)
                        ],
                    },
                    {
                        "key": "menuItems",
                        "valueMap": [
                            {
                                "key": f"item{index}",
                                "valueMap": [
                                    {"key": "name", "valueString": item["name"]},
                                    {
                                        "key": "dietaryNote",
                                        "valueString": item.get("dietary_note", ""),
                                    },
                                ],
                            }
                            for index, item in enumerate(menu_items, start=1)
                        ],
                    },
                ],
            }
        },
    ]


# Author of the events carrying the roster. Matches the RemoteA2aAgent name in
# app/agent.py; a rename there silently disables the attendee check below.
SCHEDULING_AGENT_NAME = "scheduling_agent"


def _scheduling_agent_text(tool_context: ToolContext) -> str:
    """Concatenates what the scheduling agent said during this invocation."""
    session = getattr(tool_context, "session", None)
    if session is None:
        return ""

    chunks: list[str] = []
    for event in session.events or []:
        if event.author != SCHEDULING_AGENT_NAME:
            continue
        if event.invocation_id != tool_context.invocation_id:
            continue
        for part in getattr(event.content, "parts", None) or []:
            if part.text:
                chunks.append(part.text)
    return "\n".join(chunks)


def _unsupported_attendees(attendees: list[str], roster_text: str) -> list[str]:
    """Returns the attendees the scheduling agent never mentioned.

    Matched whole, not per-word: an invented "Jordan Taylor" must not pass on the
    strength of a real "Jordan". Callers skip the check when the scheduling agent
    produced nothing, since there is then no roster to judge against.
    """
    haystack = roster_text.casefold()
    return [name for name in attendees if name.casefold() not in haystack]


# The roster line STEP 3b makes the scheduling agent open its shortlist with,
# e.g. "Team (8): Liam, Diego, Dan, ...". Markdown emphasis around it is common
# enough from the model that the separators are matched loosely.
_ROSTER_LINE = re.compile(
    r"Team\s*\**\s*\(\s*(\d+)\s*\)\s*\**\s*:\s*(.+)", re.IGNORECASE
)


def _split_names(text: str) -> list[str]:
    """Splits a written list of names, tolerating "and" and trailing punctuation."""
    return [
        stripped
        for name in re.split(r",|\band\b", text)
        if (stripped := name.strip(" .;*_`"))
    ]


def _roster_from_text(roster_text: str) -> list[str] | None:
    """Reads the roster the scheduling agent named, or None if it didn't name one.

    Deliberately not derived from the slot labels: a check the model can satisfy
    by rewriting its own label ("4 of 4 free") constrains nothing.
    """
    for line in roster_text.splitlines():
        match = _ROSTER_LINE.search(line)
        if not match:
            continue
        names = _split_names(match.group(2))
        if len(names) == int(match.group(1)):
            return names
    return None


def propose_lunch(
    title: str,
    rationale: str,
    attendees: list[str],
    slot_labels: list[str],
    slot_values: list[str],
    slot_absentees: list[str],
    recommended_slot: str,
    menu_names: list[str],
    menu_notes: list[str],
    tool_context: ToolContext,
) -> str:
    """Renders the team lunch proposal to the user as an interactive card.

    Every argument is a flat list of strings. Lists that pair up (slot_labels with
    slot_values and slot_absentees, menu_names with menu_notes) must be the same
    length and in the same order -- entry i of one describes entry i of the other.

    Args:
        title: Short name for the lunch, referencing the strategic objective it serves.
        rationale: One or two sentences on which corporate priority this lunch advances.
        attendees: The team exactly as the scheduling agent's "Team (N): ..." line
            names it, one per entry, copied verbatim -- do not expand a first name
            into a full name, invent anyone, or use a placeholder. This is the whole
            team, not the subset free at the recommended slot.
        slot_labels: Human-readable label per time slot, with attendance included
            (e.g. "Tue 12 Aug, 12:00-13:00 (8 of 8 free)"). Include ALL viable options
            you were given, typically 2-4 -- these render as a picker the user chooses
            from, so a single slot leaves nothing to choose.
        slot_values: ISO timestamp per slot (e.g. "2026-08-12T12:00"), same order and
            length as slot_labels.
        slot_absentees: Who cannot attend each slot, same order and length as
            slot_labels -- the names the scheduling agent gave for that slot,
            comma-separated (e.g. "Maya, Kai"). Use an empty string for a slot the
            whole team can make. Every name must be one the scheduling agent
            listed.
        recommended_slot: The slot_values entry you recommend; must be one of them.
        menu_names: Dish name per catering option.
        menu_notes: The dietary restriction each dish accommodates (e.g. "Gluten-free"),
            same order and length as menu_names.
    """
    try:
        if len(slot_labels) != len(slot_values):
            raise ValueError(
                f"slot_labels has {len(slot_labels)} entries but slot_values has "
                f"{len(slot_values)}; they must correspond one to one"
            )
        if len(slot_absentees) != len(slot_labels):
            raise ValueError(
                f"slot_absentees has {len(slot_absentees)} entries but slot_labels has "
                f"{len(slot_labels)}; give one entry per slot, empty where everyone "
                f"can attend"
            )
        if len(menu_names) != len(menu_notes):
            raise ValueError(
                f"menu_names has {len(menu_names)} entries but menu_notes has "
                f"{len(menu_notes)}; they must correspond one to one"
            )
        roster_text = _scheduling_agent_text(tool_context)
        roster = _roster_from_text(roster_text)
        if roster is not None:
            missing = [n for n in roster if n.casefold() not in {a.casefold() for a in attendees}]
            extra = [a for a in attendees if a.casefold() not in {n.casefold() for n in roster}]
            if missing or extra:
                raise ValueError(
                    f"attendees must be exactly the team the scheduling agent named "
                    f"({', '.join(roster)})"
                    + (f"; missing {', '.join(missing)}" if missing else "")
                    + (f"; not on the team: {', '.join(extra)}" if extra else "")
                )
        elif roster_text:
            # No roster line to match against, so only inventions can be caught.
            invented = _unsupported_attendees(attendees, roster_text)
            if invented:
                raise ValueError(
                    f"these attendees are not on the roster the scheduling agent "
                    f"returned: {', '.join(invented)}. Use the names it gave you, "
                    f"spelled the same way"
                )
        # An absentee is a team member, so it is held to the same roster as
        # attendees -- an invented name is no more acceptable for who is missing
        # than for who is coming.
        if roster is not None:
            known = {n.casefold() for n in roster}
            unknown = [
                name
                for entry in slot_absentees
                for name in _split_names(entry)
                if name.casefold() not in known
            ]
            if unknown:
                raise ValueError(
                    f"slot_absentees names people who are not on the team: "
                    f"{', '.join(unknown)}. Use only the names in "
                    f"({', '.join(roster)})"
                )
        payload = build_lunch_surface(
            title=title,
            rationale=rationale,
            attendees=attendees,
            time_slots=[
                {"label": label, "value": value, "absent": absent}
                for label, value, absent in zip(slot_labels, slot_values, slot_absentees)
            ],
            recommended_slot=recommended_slot,
            menu_items=[
                {"name": name, "dietary_note": note}
                for name, note in zip(menu_names, menu_notes)
            ],
        )
    except (ValueError, KeyError, TypeError) as error:
        # Returned to the model so it can correct the arguments and retry.
        return f"Could not render the proposal: {error}"

    tool_context.state[PAYLOAD_STATE_KEY] = payload
    return "Proposal rendered for the user."


propose_lunch_tool = FunctionTool(propose_lunch)


def _without_a2ui(part: Part) -> Part | None:
    """Strips an A2UI block from a part, returning None if nothing else remains."""
    text = part.text
    if not text or A2UI_OPEN_TAG not in text:
        return part

    start = text.find(A2UI_OPEN_TAG)
    end = text.find(A2UI_CLOSE_TAG, start)
    remainder = (
        text[:start] + (text[end + len(A2UI_CLOSE_TAG):] if end != -1 else "")
    ).strip()
    return part.model_copy(update={"text": remainder}) if remainder else None


class A2uiHistoryPlugin(BasePlugin):
    """Keeps emitted A2UI surfaces out of the history sent back to the model.

    The surface has to reach the client as ``<a2ui-json>`` in the message text --
    that is the only form the ADK dev UI renders -- so it lands in the session
    event. Left alone, the whole component tree is then replayed as context on
    every later turn: measured at ~3,400 characters, roughly 2,200 prompt tokens,
    per call for the remainder of the conversation.

    Nothing downstream needs it back. The client has already rendered it, and the
    model gets no use from re-reading its own markup -- if anything it invites
    imitation, against an instruction that says not to emit JSON.

    Stored events are untouched; this only trims the request.
    """

    def __init__(self) -> None:
        super().__init__(name="a2ui_history")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        trimmed = []
        for content in llm_request.contents:
            parts = content.parts or []
            kept = []
            changed = False
            for part in parts:
                stripped = _without_a2ui(part)
                # Identity, not length: a part can be rewritten without being dropped.
                changed = changed or stripped is not part
                if stripped is not None:
                    kept.append(stripped)
            if not changed:
                trimmed.append(content)
            elif kept:
                # Copied rather than mutated: these may be the session's own objects.
                trimmed.append(content.model_copy(update={"parts": kept}))
        llm_request.contents = trimmed
        return None


def a2ui_emit_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Appends the built A2UI payload to the model's closing summary.

    The tool stores the payload in session state; this attaches it to the next
    text-only response as an ``<a2ui-json>`` block, which is the form the ADK dev
    UI renders. Conversion to A2A data parts for Gemini Enterprise still happens
    at the A2A boundary (see ``a2ui_gen_ai_part_converter``).
    """
    if llm_response is None or llm_response.partial:
        return None

    content = llm_response.content

    # The turn that *calls* the tool carries function calls and no summary yet. Leave
    # the payload in place for the response that follows.
    if content and any(part.function_call for part in content.parts or []):
        return None

    payload = callback_context.state.get(PAYLOAD_STATE_KEY)
    if not payload:
        return None

    # Consumed here, not after a successful attach. A response the payload cannot be
    # attached to -- no content, no parts, or one that already carries a block -- means
    # this surface is spent; leaving it in state would render it on some later turn,
    # against whatever the user asked next.
    callback_context.state[PAYLOAD_STATE_KEY] = None

    if content is None or not content.parts:
        return None

    if any(A2UI_OPEN_TAG in (part.text or "") for part in content.parts):
        return None

    block = A2UI_OPEN_TAG + json.dumps(payload) + A2UI_CLOSE_TAG
    # Appended as its own part rather than rebuilding content.parts, which would drop
    # thought signatures and any non-text part, and would fold the text of thought parts
    # into the answer -- google.genai's own `.text` accessor excludes those.
    return llm_response.model_copy(
        update={
            "content": content.model_copy(
                update={"parts": [*content.parts, Part(text=block)]}
            )
        }
    )
