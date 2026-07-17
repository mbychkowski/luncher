import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool

# Load environment variables
load_dotenv()

# Retrieve remote agent URLs, defaulting to standard local dev ports
STRAT_AGENT_URL = os.getenv("STRAT_AGENT_URL", "http://localhost:8080")
SCHED_AGENT_URL = os.getenv("SCHED_AGENT_URL", "http://localhost:8081")

# Instantiate A2A connectors to the specialized sub-agents
strategy_agent_connector = RemoteA2aAgent(
    name="strategy_agent",
    description="Inspects and synthesizes corporate strategy PDF documents to extract business constraints and priorities.",
    agent_card=f"{STRAT_AGENT_URL}/.well-known/agent-card.json"
)

scheduling_agent_connector = RemoteA2aAgent(
    name="scheduling_agent",
    description="Interactively schedules team meetings, checks dietary preferences/schedules, and books catering.",
    agent_card=f"{SCHED_AGENT_URL}/.well-known/agent-card.json"
)

# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model="gemini-2.5-flash",
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
    tools=[AgentTool(strategy_agent_connector), AgentTool(scheduling_agent_connector)]
)

root_agent = luncher_agent

