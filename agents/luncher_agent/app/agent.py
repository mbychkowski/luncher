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

import logging
import os
from dotenv import load_dotenv

import httpx

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.apps.app import App
from google.adk.models.google_llm import Gemini
from google.genai.types import (
    HttpRetryOptions,
    ThinkingConfig,
    ThinkingLevel,
)

from .app_utils.genai_transport import GenaiApiTransport
from .proposal_builder import (
    ROLE_DESCRIPTION as SYNTHESIZER_INSTRUCTION,
    format_lunch_proposal_tool,
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


def format_agent_runtime_url(
    engine_id_or_resource: str,
    project_id: str | None = None,
    location: str | None = None,
    app_name: str = "app",
) -> str:
    """Constructs the A2A agent card URL from an Agent Runtime / Reasoning Engine unique ID."""
    clean_id = engine_id_or_resource.strip()
    if clean_id.startswith("projects/"):
        parts = clean_id.split("/")
        loc = parts[3] if len(parts) > 3 else (location or "us-central1")
        resource_path = clean_id
    else:
        proj = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
        loc = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        resource_path = f"projects/{proj}/locations/{loc}/reasoningEngines/{clean_id}"
    return (
        f"https://{loc}-aiplatform.googleapis.com/reasoningEngines/v1/"
        f"{resource_path}/api/a2a/{app_name}/.well-known/agent-card.json"
    )


def discover_sub_agent(
    agent_name: str,
    default_local_url: str,
    description: str,
    app_name: str = "app",
) -> RemoteA2aAgent:
    """Instantiates a RemoteA2aAgent using Agent Runtime Engine ID, URL, or local fallback.

    Checks:
    1. Agent Runtime unique IDs: {AGENT_NAME}_ENGINE_ID, {AGENT_NAME}_RUNTIME_ID,
       and common aliases (e.g. STRATEGY_AGENT_ENGINE_ID, STRAT_AGENT_ENGINE_ID).
    2. Direct URL env vars: {AGENT_NAME}_URL, {AGENT_NAME}_AGENT_URL.
    3. Falls back to default_local_url for local offline development.
    """
    name_upper = agent_name.upper()
    stem = name_upper.replace("_AGENT", "")
    stems = [stem]
    if stem.startswith("STRAT") and "STRAT" not in stems:
        stems.append("STRAT")
    if stem.startswith("STRAT") and "STRATEGY" not in stems:
        stems.append("STRATEGY")
    if stem.startswith("SCHED") and "SCHED" not in stems:
        stems.append("SCHED")
    if stem.startswith("SCHED") and "SCHEDULING" not in stems:
        stems.append("SCHEDULING")
    if stem.startswith("CATER") and "CATER" not in stems:
        stems.append("CATER")
    if stem.startswith("CATER") and "CATERING" not in stems:
        stems.append("CATERING")

    engine_id_vars = []
    for s in stems:
        for suffix in ("_AGENT_ENGINE_ID", "_AGENT_RUNTIME_ID", "_ENGINE_ID", "_RUNTIME_ID"):
            var = f"{s}{suffix}"
            if var not in engine_id_vars:
                engine_id_vars.append(var)

    engine_id = None
    engine_var_used = None
    for var in engine_id_vars:
        val = os.getenv(var)
        if val:
            engine_id = val
            engine_var_used = var
            break

    if engine_id:
        agent_url = format_agent_runtime_url(engine_id, app_name=app_name)
        logger.info(
            "Connecting '%s' via %s (%s): %s",
            agent_name,
            engine_var_used,
            engine_id,
            agent_url,
        )
    else:
        url_vars = []
        for s in stems:
            for suffix in ("_AGENT_URL", "_URL"):
                var = f"{s}{suffix}"
                if var not in url_vars:
                    url_vars.append(var)

        explicit_url = None
        url_var_used = None
        for var in url_vars:
            val = os.getenv(var)
            if val:
                explicit_url = val
                url_var_used = var
                break

        agent_url = explicit_url or default_local_url
        if os.getenv("GOOGLE_CLOUD_AGENT_ENGINE_ID") and not explicit_url:
            logger.warning(
                "Running in Agent Runtime cloud container, but no Engine ID or URL configured for '%s'. "
                "Defaulting to %s, which may not be reachable.",
                agent_name,
                agent_url,
            )
        logger.info(
            "Connecting '%s' via %s: %s",
            agent_name,
            url_var_used if explicit_url else f"default ({engine_id_vars[0]} unset)",
            agent_url,
        )

    if "aiplatform.googleapis.com" in agent_url:
        # An Agent Runtime peer. Its endpoint rejects a bearer header built from
        # ADC under Agent Identity, so the request goes through the genai
        # client's transport instead -- see app_utils.genai_transport.
        client = httpx.AsyncClient(
            transport=GenaiApiTransport.from_url(agent_url), timeout=120.0
        )
        logger.info("  '%s' authenticates via GenaiApiTransport", agent_name)
    else:
        # Local development unauthenticated client
        client = httpx.AsyncClient(timeout=120.0)
        logger.info("  '%s' uses local unauthenticated transport", agent_name)

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

# Stage 2: synthesize into a structured Markdown lunch proposal. The model
# calls `format_lunch_proposal` with domain data and Python validates and formats
# the proposal (app/proposal_builder.py).
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
    tools=[format_lunch_proposal_tool],
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
)


