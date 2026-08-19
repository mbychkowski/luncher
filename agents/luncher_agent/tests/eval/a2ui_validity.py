"""Deterministic metric for `a2ui_payload_valid` (see eval_config.yaml).

Scores whether the response actually carries a renderable A2UI surface. No model
call, so it is free, fast and flake-free -- which matters because the interesting
measurement is a *failure rate* over many runs, not a score on one.

Score is 0 or 1:
  1  an A2UI block is present, validates against the v0.8 standard catalog, and
     has no binding problems
  0  missing, malformed, schema-invalid, or structurally valid but non-functional
"""

import json
import sys
from pathlib import Path

# Locating the agent package has to survive both runners: `adk eval` imports this
# module, while `agents-cli eval grade` compiles its source, leaving __file__
# undefined. The CLI resolves its project from the working directory, so that is
# the package root whenever the file's own path is unavailable.
_AGENT_ROOT = (
    Path(__file__).resolve().parents[2] if "__file__" in globals() else Path.cwd()
)
sys.path.insert(0, str(_AGENT_ROOT))

from app.a2ui import A2UI_FORMAT, find_binding_problems  # noqa: E402

# The three message kinds a surface is built from.
_MESSAGE_KINDS = {"beginRendering", "surfaceUpdate", "dataModelUpdate"}

OPEN_TAG = "<a2ui-json>"
CLOSE_TAG = "</a2ui-json>"


def _response_text(response) -> str:
    """Reduces a response to its text, however the runner shaped it.

    Serialising a structured response instead would escape the payload's quotes,
    so the block is still found and no longer parses -- a surface that renders
    perfectly then scores zero.
    """
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        return "".join(_response_text(item) for item in response)
    if isinstance(response, dict):
        inner = response.get("response")
        if isinstance(inner, (dict, list)):
            return _response_text(inner)
        parts = response.get("parts") or []
        return "".join(
            part.get("text") or "" for part in parts if isinstance(part, dict)
        )
    return ""


def _a2ui_data_parts(response) -> list:
    """Collects A2UI messages delivered as data parts.

    Over A2A the surface arrives converted -- one data part per message -- rather
    than as the <a2ui-json> text the dev UI renders from. Reading both means the
    same metric grades either path, and on A2A it also proves the conversion at
    that boundary.
    """
    if isinstance(response, list):
        return [m for item in response for m in _a2ui_data_parts(item)]
    if isinstance(response, dict):
        inner = response.get("response")
        if isinstance(inner, (dict, list)):
            return _a2ui_data_parts(inner)
        messages = []
        for part in response.get("parts") or []:
            data = part.get("data") if isinstance(part, dict) else None
            if isinstance(data, dict) and data.keys() & _MESSAGE_KINDS:
                messages.append(data)
        return messages
    return []


def _extract(response) -> list | None:
    if messages := _a2ui_data_parts(response):
        return messages

    text = _response_text(response)
    start = text.find(OPEN_TAG)
    if start == -1:
        return None
    end = text.find(CLOSE_TAG, start + len(OPEN_TAG))
    if end == -1:
        return None
    try:
        payload = json.loads(text[start + len(OPEN_TAG) : end])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else [payload]


def evaluate(instance):
    payload = _extract(instance.get("response", ""))
    if payload is None:
        return {"score": 0, "explanation": "No parseable <a2ui-json> block in the response."}

    try:
        A2UI_FORMAT.get_selected_catalog().validator.validate(payload)
    except Exception as error:  # A2uiValidationError and friends
        return {"score": 0, "explanation": f"Catalog validation failed: {error}"}

    if problems := find_binding_problems(payload):
        return {"score": 0, "explanation": "; ".join(problems)}

    kinds = [next(iter(message)) for message in payload if isinstance(message, dict)]
    return {
        "score": 1,
        "explanation": f"Valid A2UI surface, bindings clean, messages: {kinds}.",
    }
