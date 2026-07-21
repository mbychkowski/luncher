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

import os
import httpx
import google.auth.transport.requests
import google.oauth2.id_token
from dotenv import load_dotenv
from a2a.types import AgentCard, AgentCapabilities
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool

# Load environment variables
load_dotenv()

def resolve_subagent_url(env_var_name: str, display_name: str, default_local: str) -> str:
    """Resolve subagent URL from env var, or dynamically from Vertex AI by display_name."""
    url = os.getenv(env_var_name)
    if url:
        return url
        
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    if project_id:
        try:
            import vertexai
            from vertexai.preview import reasoning_engines
            vertexai.init(project=project_id, location=location)
            engines = reasoning_engines.ReasoningEngine.list()
            for e in engines:
                if e.display_name == display_name:
                    resource = e.resource_name if e.resource_name.endswith(":query") else f"{e.resource_name}:query"
                    discovered = f"https://{location}-aiplatform.googleapis.com/v1/{resource}"
                    print(f"[luncher_agent] Discovered {display_name} URL: {discovered}")
                    return discovered
        except Exception as err:
            print(f"[luncher_agent] Dynamic discovery for {display_name} failed: {err}")
            
    return default_local

# Retrieve remote agent URLs dynamically on GCP or default to standard local ports
STRAT_AGENT_URL = resolve_subagent_url("STRAT_AGENT_URL", "strat-agent", "http://localhost:8080")
SCHED_AGENT_URL = resolve_subagent_url("SCHED_AGENT_URL", "sched-agent", "http://localhost:8081")

def get_agent_card_url(base_url: str) -> str:
    if "v1/card" in base_url or base_url.endswith(".json"):
        return base_url
    return f"{base_url.rstrip('/')}/.well-known/agent-card.json"

def fetch_agent_card(base_url: str) -> str | AgentCard:
    """Fetch agent card with authentication if targeting a GCP Cloud Run endpoint."""
    if "localhost" in base_url or "0.0.0.0" in base_url:
        return base_url

    # Reasoning Engine endpoints do not serve agent-card.json; return explicit AgentCard
    if "aiplatform.googleapis.com" in base_url:
        return AgentCard(
            name="remote_reasoning_engine",
            description="Remote Vertex AI Reasoning Engine sub-agent",
            url=base_url,
            version="1.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(),
            skills=[],
        )
        
    card_url = get_agent_card_url(base_url)
    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, base_url)
    headers = {"Authorization": f"Bearer {id_token}"}
        
    resp = httpx.get(card_url, headers=headers)
    resp.raise_for_status()
    return AgentCard.model_validate(resp.json())

def get_httpx_client(base_url: str) -> httpx.AsyncClient | None:
    """Create authenticated httpx.AsyncClient for outbound A2A RPC calls."""
    if "aiplatform.googleapis.com" in base_url:
        auth_req = google.auth.transport.requests.Request()
        credentials, _ = google.auth.default()
        credentials.refresh(auth_req)
        return httpx.AsyncClient(timeout=60.0, headers={"Authorization": f"Bearer {credentials.token}"})
    elif not ("localhost" in base_url or "0.0.0.0" in base_url):
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, base_url)
        return httpx.AsyncClient(timeout=60.0, headers={"Authorization": f"Bearer {id_token}"})
    return None

import sys

# Ensure repository root is on sys.path for sub-agent imports
current_file = os.path.abspath(__file__)
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Resolve sub-agent tools (in-process or remote A2A connectors)
try:
    from agents.strat_agent.main import strategy_agent
    from agents.sched_agent.main import scheduling_agent
    print("[luncher_agent] Loaded strategy_agent and scheduling_agent in-process.")
    strat_tool = AgentTool(strategy_agent)
    sched_tool = AgentTool(scheduling_agent)
except Exception as err:
    print(f"[luncher_agent] Falling back to remote A2A connectors: {err}")
    strategy_agent_connector = RemoteA2aAgent(
        name="strategy_agent",
        description="Inspects and synthesizes corporate strategy PDF documents to extract business constraints and priorities.",
        agent_card=fetch_agent_card(STRAT_AGENT_URL),
        httpx_client=get_httpx_client(STRAT_AGENT_URL),
    )

    scheduling_agent_connector = RemoteA2aAgent(
        name="scheduling_agent",
        description="Interactively schedules team meetings, checks dietary preferences/schedules, and books catering.",
        agent_card=fetch_agent_card(SCHED_AGENT_URL),
        httpx_client=get_httpx_client(SCHED_AGENT_URL),
    )
    strat_tool = AgentTool(strategy_agent_connector)
    sched_tool = AgentTool(scheduling_agent_connector)

from google.adk.models.google_llm import Gemini
from google.genai.types import HttpRetryOptions

default_retry_policy = HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503]
)

# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=default_retry_policy),
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    instruction=(
        "You are the central Luncher Orchestrator Agent. Your job is to act as the primary user-facing frontend "
        "to schedule team lunches that are strategically aligned with corporate priorities.\n\n"
        
        "Your available tools:\n"
        "1. 'strategy_agent' - Use this to retrieve corporate strategic objectives, launch dates, or corporate priorities.\n"
        "2. 'scheduling_agent' - Use this to manage team schedules, check/update dietary preferences, and finalize bookings.\n\n"
        
        "COORDINATION PROTOCOL:\n"
        "- When a user asks you to plan/schedule a team lunch or meeting, you MUST ALWAYS consult the strategy_agent first to identify any relevant corporate priorities or initiatives.\n"
        "- Next, delegate to the scheduling_agent to identify the optimal overlapping time slot and catering options for the team based on those priorities.\n"
        "- Synthesize the information into a single cohesive response, framing the lunch proposal around the identified strategic objectives (e.g., 'To align with our strategy on the OmniChef launch, I recommend...').\n"
        "- If the user accepts, delegate the final booking execution to the scheduling_agent."
    ),
    tools=[strat_tool, sched_tool]
)

root_agent = luncher_agent
