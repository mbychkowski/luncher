import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

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

def consult_strategy_agent(query: str) -> str:
    """Consults the Strategy Agent to retrieve corporate plans, launch objectives, or business priorities.
    
    Args:
        query: The request to ask the Strategy Agent (e.g. 'What are the main products/dates for the upcoming launches?').
    """
    print(f"[Orchestrator] Delegating to Strategy Agent: '{query}'")
    try:
        return strategy_agent_connector.call(query)
    except Exception as e:
        return f"Error contacting Strategy Agent: {str(e)}. Please proceed with general scheduling instead."

def delegate_to_scheduling_agent(query: str) -> str:
    """Delegates meeting scheduling, catering selection, preference updates, and booking to the Scheduling Agent.
    
    Args:
        query: The request to ask the Scheduling Agent (e.g. 'Schedule a team lunch for Alice, Bob, and Charlie.').
    """
    print(f"[Orchestrator] Delegating to Scheduling Agent: '{query}'")
    try:
        return scheduling_agent_connector.call(query)
    except Exception as e:
        return f"Error contacting Scheduling Agent: {str(e)}"

# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model="gemini-2.5-flash",
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    instruction=(
        "You are the central Luncher Orchestrator Agent. Your job is to act as the primary user-facing frontend "
        "to schedule team lunches that are strategically aligned with corporate priorities.\n\n"
        
        "Your available tools:\n"
        "1. 'consult_strategy_agent' - Use this to retrieve corporate strategic objectives, launch dates, or corporate priorities.\n"
        "2. 'delegate_to_scheduling_agent' - Use this to manage team schedules, check/update dietary preferences, and finalize bookings.\n\n"
        
        "COORDINATION PROTOCOL:\n"
        "- When a user asks you to plan/schedule a team lunch or meeting, you MUST ALWAYS consult the Strategy Agent first to identify any relevant corporate priorities or initiatives.\n"
        "- Next, delegate to the Scheduling Agent to identify the optimal overlapping time slot and catering options for the team based on those priorities.\n"
        "- Synthesize the information into a single cohesive response, framing the lunch proposal around the identified strategic objectives (e.g., 'To align with our strategy on the OmniChef launch, I recommend...').\n"
        "- If the user accepts, delegate the final booking execution to the Scheduling Agent."
    ),
    tools=[consult_strategy_agent, delegate_to_scheduling_agent]
)

root_agent = luncher_agent
