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
import vertexai

import httpx
import google.auth
from google.auth.transport.requests import Request

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.apps.app import App
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool, load_memory, ToolContext
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part, HttpRetryOptions, ThinkingConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Gemini Enterprise Agent Platform (GEAP) & GCP Project configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_LOCATION = os.getenv("GOOGLE_GENAI_LOCATION", "global")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

vertexai.init(project=PROJECT_ID, location=LOCATION)


async def save_food_preference(preference: str, tool_context: ToolContext) -> str:
    """Saves a team member's food preference or allergy to the memory store.

    Args:
        preference: The food preference statement to save (e.g., 'Alice is allergic to dairy').
    """
    content = Content(parts=[Part(text=preference)], role="user")
    try:
        entry = MemoryEntry(content=content)
        await tool_context.add_memory(memories=[entry])
    except (NotImplementedError, ValueError):
        from google.adk.events import Event
        event = Event(content=content, author="user")
        await tool_context.add_events_to_memory(events=[event])
    return f"Saved food preference: {preference}"

save_food_preference_tool = FunctionTool(save_food_preference)


def _get_auth_headers(url: str) -> dict[str, str]:
    headers = {}
    if "aiplatform.googleapis.com" in url:
        try:
            creds, _ = google.auth.default()
            req = Request()
            creds.refresh(req)
            if creds.token:
                headers["Authorization"] = f"Bearer {creds.token}"
        except Exception as e:
            logger.warning(f"Could not fetch OAuth access token for {url}: {e}")
    elif "run.app" in url:
        target_audience = url.split("/a2a")[0].split("/.well-known")[0]
        # First try Compute Metadata Server (active on Cloud Run & Agent Runtime)
        try:
            meta_url = f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={target_audience}"
            meta_resp = httpx.get(meta_url, headers={"Metadata-Flavor": "Google"}, timeout=5.0)
            if meta_resp.status_code == 200 and meta_resp.text:
                headers["Authorization"] = f"Bearer {meta_resp.text.strip()}"
                return headers
        except Exception:
            pass

        # Fallback to id_token or OAuth token
        try:
            from google.oauth2 import id_token
            req = Request()
            token = id_token.fetch_id_token(req, target_audience)
            headers["Authorization"] = f"Bearer {token}"
        except Exception:
            try:
                creds, _ = google.auth.default()
                creds.refresh(Request())
                if creds.token:
                    headers["Authorization"] = f"Bearer {creds.token}"
            except Exception as e:
                logger.warning(f"Could not fetch auth token for Cloud Run {url}: {e}")
    return headers


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
    logger.info(f"Connecting '{agent_name}' using direct URL: {agent_url}")

    headers = _get_auth_headers(agent_url)
    client = httpx.AsyncClient(headers=headers, timeout=120.0) if headers else httpx.AsyncClient(timeout=120.0)

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
        "Helps coordinate meeting times and catering food preferences across team members interactively."
    ),
)

default_retry_policy = HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503],
)

# Stage 1: Memory retrieval agent (with thinking_budget=0 for zero reasoning latency)
memory_agent = Agent(
    model=Gemini(
        model="gemini-3.5-flash",
        thinking_config=ThinkingConfig(thinking_budget=0),
        retry_options=default_retry_policy,
        client_kwargs={"location": MODEL_LOCATION},
    ),
    name="memory_agent",
    description="Retrieves saved team food preferences from memory bank or records new food preferences.",
    instruction=(
        "You are the Memory & Preference Retrieval Agent. Your job is to check user input for food preferences "
        "and retrieve all saved team member food preferences from memory.\n\n"
        "ROUTING AND PREFERENCE SAVING PROTOCOL:\n"
        "- If the user prompt specifies a food preference or allergy (e.g., 'Alice is allergic to dairy' or 'Bob dislikes spicy food'), call the `save_food_preference` tool to save it to memory, then confirm the saved preference.\n\n"
        "RETRIEVAL & OUTPUT PROTOCOL:\n"
        "- Call `load_memory` to fetch all saved team member food preferences, dietary restrictions, and allergies.\n"
        "- OUTPUT RULES:\n"
        "  1. If no saved preferences or memories are found, output exactly one short line: 'Checked memory: no saved dietary preferences.'\n"
        "  2. If saved preferences exist, provide a brief 1-line summary of the saved preferences (e.g., 'Retrieved preferences: Alice (dairy allergy)'). Do NOT add filler text or conversational narrative."
    ),
    tools=[
        save_food_preference_tool,
        load_memory,
    ],
)

# Stage 1 (Parallel): Gather corporate strategy, scheduling options, and food preference memories concurrently
parallel_sub_agents = ParallelAgent(
    name="parallel_info_gatherer",
    description="Gathers corporate strategy context, team availability, and saved food preferences concurrently.",
    sub_agents=[memory_agent, strategy_agent, scheduling_agent],
)

# Stage 2: Synthesize findings into a strategy-aligned lunch proposal (thinking_budget=0 for zero reasoning latency)
synthesizer_agent = Agent(
    model=Gemini(
        model="gemini-3.5-flash",
        thinking_config=ThinkingConfig(thinking_budget=0),
        retry_options=default_retry_policy,
        client_kwargs={"location": MODEL_LOCATION},
    ),
    name="lunch_synthesizer",
    description="Synthesizes corporate strategy objectives, scheduling options, and retrieved team memories into a team lunch proposal.",
    instruction=(
        "You are the central Luncher Synthesizer Agent. You receive context containing retrieved team food preferences from memory, "
        "strategic corporate priorities, and team schedule options.\n\n"
        "YOUR ROLE:\n"
        "- Synthesize the strategic priorities (e.g. OmniChef launch, VisionSphere), scheduling availability, and retrieved food preferences into a single cohesive response.\n"
        "- Explicitly list the names of all team members who are included in the event/meeting (e.g., 'Included Team Members: Liam, Diego, Dan, Maya, Aaliyah, Naomi, Jordan, Kai').\n"
        "- Frame the proposed team lunch around the identified strategic objectives (e.g., 'To align with our strategy on the OmniChef launch, I recommend...').\n"
        "- Present clear time slots and in-house catering menu recommendations matching all saved team food preferences."
    ),
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


