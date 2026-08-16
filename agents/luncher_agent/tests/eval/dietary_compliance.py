"""LLM-as-judge for `dietary_compliance` (see eval_config.yaml).

The one thing neither the catalog validator nor the builder can check: whether the
proposed menu is actually *safe*. Structure is guaranteed by construction; content
is not, and a dish that violates a stated allergy is the highest-consequence
failure this agent can produce.

Follows the same shape as response_quality.py -- temperature 0 and a response
schema, so grading is deterministic and always parseable.
"""

import os

from google import genai
from google.genai import types
from pydantic import BaseModel

# Follows the agents' own configuration rather than pinning its own. The model
# they run is served only from the `global` endpoint, and a regional one answers
# 404 "Publisher model ... was not found", which reads as a bad model name.
_MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-3.6-flash")


def _client() -> genai.Client:
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
        return genai.Client(location=os.getenv("GOOGLE_GENAI_LOCATION", "global"))
    return genai.Client()  # AI Studio (GEMINI_API_KEY)


class _Verdict(BaseModel):
    score: int  # 1-5
    violations: str
    explanation: str


RUBRIC = """
You are auditing a team lunch proposal for dietary safety.

Grade 1-5:
  5  every stated restriction is accommodated by at least one dish, and each dish
     names the restriction it satisfies; nothing contradicts a stated restriction
  3  restrictions are broadly handled but labelling is vague, incomplete, or a
     diner would have to guess what is safe for them
  1  a dish violates a stated restriction, or a stated restriction has no safe
     option at all

Judge only dietary safety and labelling. Ignore layout, wording and tone.
If the user stated no restrictions, grade whether the menu is sensibly inclusive
without inventing restrictions that were never mentioned.
List any concrete violations in `violations`, or "none".
"""


def evaluate(instance):
    prompt = (
        f"{RUBRIC}\n"
        f"User request (contains the stated restrictions): {instance.get('prompt', '')}\n"
        f"Expected behaviour: {instance.get('reference', '')}\n"
        f"Agent response (the proposal, including its A2UI payload): "
        f"{instance.get('response', '')}\n"
    )

    # Held in a local: the client owns the transport, and letting it go out of
    # scope closes it under the request.
    client = _client()
    response = client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=_Verdict,
        ),
    )
    verdict = response.parsed
    if verdict is None:
        return {"score": 0, "explanation": response.text or "judge returned nothing"}
    return {
        "score": max(1, min(5, verdict.score)),
        "explanation": f"{verdict.explanation} | violations: {verdict.violations}",
    }
