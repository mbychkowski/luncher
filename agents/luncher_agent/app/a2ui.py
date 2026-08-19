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

"""Shared A2UI v0.8 plumbing: catalog, validation, and the A2A boundary.

Gemini Enterprise renders agent-authored UI via A2UI and supports **only** v0.8
with the standard catalog. Surfaces are constructed deterministically in
:mod:`app.a2ui_builder`; this module owns the pieces both that builder and the
serving surfaces depend on:

* :data:`A2UI_FORMAT` -- the catalog, used for validation.
* :func:`find_binding_problems` -- catches schema-valid but non-functional
  bindings that the catalog validator cannot.
* :func:`a2ui_gen_ai_part_converter` -- converts tagged text into
  ``application/json+a2ui`` data parts, wired in at the A2A boundary only.

The v0.8 standard catalog has 18 components. Notably it has **no** ``Table``,
``Heading``, ``ChoicePicker`` or ``GoogleMap`` despite those appearing in some
Google documentation -- use ``List``/``Column`` and ``MultipleChoice`` instead.
"""

from __future__ import annotations

import logging
import os

from a2ui.adk.a2a.part_converter import A2uiPartConverter
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json import DirectJsonFormat
from a2ui.schema.catalog import VERSION_0_8
from a2ui.schema.common_modifiers import remove_strict_validation

logger = logging.getLogger(__name__)

# Golden A2UI payload used as a test fixture. No longer feeds a prompt.
EXAMPLES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "examples", VERSION_0_8
)

def build_a2ui_format() -> DirectJsonFormat:
    """Returns the A2UI v0.8 format bound to the standard catalog."""
    return DirectJsonFormat(
        version=VERSION_0_8,
        catalogs=[BasicCatalog.get_config(version=VERSION_0_8)],
        schema_modifiers=[remove_strict_validation],
    )


# Built once at import: loading the catalog schema is not free and the format is
# stateless once constructed.
A2UI_FORMAT = build_a2ui_format()

# Component property that holds user-editable state, per v0.8 component. Bind these to
# a data model path or the user's input has nowhere to be written. ``label`` is excluded
# deliberately -- it is display text, not state.
_INTERACTIVE_STATE_PROPS = {
    "MultipleChoice": "selections",
    "CheckBox": "value",
    "TextField": "text",
    "Slider": "value",
    "DateTimeInput": "value",
}

_LITERAL_KEYS = ("literalArray", "literalString", "literalNumber", "literalBoolean")


def find_binding_problems(messages: list) -> list[str]:
    """Returns human-readable descriptions of unbound interactive state.

    Catalog validation cannot catch this: ``{"literalArray": [...]}`` and
    ``{"path": "/x"}`` are both schema-valid for a ``selections`` property. Only one
    of them actually works. A literal leaves the user's choice with nowhere to be
    stored, and an action reading a literal keeps submitting the agent's suggestion
    no matter what the user picks.
    """
    problems: list[str] = []
    components = [
        component
        for message in messages
        if isinstance(message, dict) and "surfaceUpdate" in message
        for component in message["surfaceUpdate"].get("components", [])
    ]

    # Values a user could pick, used to spot literals copied out of an option list.
    selectable_values = set()
    for entry in components:
        spec = entry.get("component") or {}
        for props in spec.values():
            for option in (props or {}).get("options") or []:
                if isinstance(option.get("value"), str):
                    selectable_values.add(option["value"])

    for entry in components:
        component_id = entry.get("id", "<unknown>")
        spec = entry.get("component") or {}
        for name, props in spec.items():
            props = props or {}

            state_prop = _INTERACTIVE_STATE_PROPS.get(name)
            if state_prop:
                binding = props.get(state_prop)
                if isinstance(binding, dict) and not binding.get("path"):
                    literal = next((k for k in _LITERAL_KEYS if k in binding), "nothing")
                    problems.append(
                        f"{name} '{component_id}' binds {state_prop} to {literal};"
                        " user input cannot be recorded. Use {'path': ...}."
                    )

            for item in (props.get("action") or {}).get("context") or []:
                value = item.get("value")
                if not isinstance(value, dict) or value.get("path"):
                    continue
                if value.get("literalString") in selectable_values:
                    problems.append(
                        f"{name} '{component_id}' sends action context"
                        f" '{item.get('key')}' as a literal copy of a selectable"
                        " value; it will ignore what the user picks."
                        " Use {'path': ...}."
                    )

    return problems


# Converts tagged A2UI text into ``application/json+a2ui`` data parts at the A2A
# boundary, so A2A consumers (Gemini Enterprise) get data parts while the dev UI keeps
# seeing the ``<a2ui-json>`` tags it renders from message text. Falls back to ADK's
# default conversion for every other kind of part.
#
# The dev UI only takes its data-part path for events carrying customMetadata
# ``a2a:response``, so the tags must stay in the text for local rendering.
#
# ``fallback_text`` covers the case where a payload fails to parse: without it the
# converter yields no parts at all and the A2A consumer receives an empty message,
# losing the surrounding prose along with the surface.
a2ui_gen_ai_part_converter = A2uiPartConverter(
    a2ui_catalog=A2UI_FORMAT.get_selected_catalog(),
    version=VERSION_0_8,
    fallback_text="The lunch proposal could not be rendered.",
).convert
