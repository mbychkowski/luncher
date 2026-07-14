"""Main agent definitions and graph-based workflow configuration for Luncher.

This file establishes the multi-agent orchestration for planning team meetings and catered lunch, 
built with ADK 2.0 graph-based workflows, parallel fan-out/fan-in, and Human-in-the-Loop gates.
"""

import os
import google.auth
from pydantic import BaseModel, Field

# ADK 2.0 Graph-based Workflow Imports
from google.adk.workflow import Workflow, node, JoinNode, START
from google.adk.agents import LlmAgent
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini

# Import our custom tool functions
from .tools import (
    query_agenda_guidelines,
    get_calendar_availability,
    search_catering,
    submit_catering_order
)

# 1. Initialize GCP Location & Authentication defaults
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# ==========================================
# 2. Structured Data Schemas (Pydantic)
# ==========================================

class MeetingRequest(BaseModel):
    purpose: str = Field(description="The meeting purpose or goals, e.g. Technical Kickoff")
    attendees: list[str] = Field(description="List of attendee names, e.g. ['Alice', 'Bob']")

class AgendaDraft(BaseModel):
    agenda_markdown: str = Field(description="Drafted chronological agenda structure with timestamps and guidelines citations")

class TeamPreferences(BaseModel):
    dietary_needs: list[str] = Field(description="Aggregated dietary requirements gathered from Memory Bank")
    suggested_time: str = Field(description="Determined 90-minute time window based on calendar checks")

class CateringDraft(BaseModel):
    restaurant: str = Field(description="The selected catering restaurant name")
    menu_items: list[str] = Field(description="List of matching food items chosen for the team")
    total_cost: float = Field(description="Calculated total order cost, complying with budget caps")


# ==========================================
# 3. Specialized Agent Personas
# ==========================================

# Agenda Agent (RAG-grounded LLM worker)
agenda_agent = LlmAgent(
    name="agenda_agent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=(
        "You are an Agenda Planning Specialist. Your job is to draft a clean chronological meeting agenda.\n"
        "1. You must query corporate guidelines using query_agenda_guidelines.\n"
        "2. Find the template that matches the user's meeting purpose (e.g. Technical Kickoff, Marketing Sync).\n"
        "3. Format the agenda, cite guidelines sections explicitly, and enforce strict timing blocks.\n"
        "4. Output must comply with AgendaDraft structure."
    ),
    tools=[query_agenda_guidelines],
    output_schema=AgendaDraft
)


# ==========================================
# 4. Workflow Node Definitions & Functions
# ==========================================

@node
def get_preferences(ctx: Context, node_input: MeetingRequest) -> TeamPreferences:
    """Node that recalls dietary requirements from ADK Memory Bank and checks calendar free/busy slots."""
    
    # ------------------ ADK MEMORY BANK WORKSHOP NOTE ------------------
    # In Exercise 3, participants will learn how to recall state persistently
    # from the active session context, which is perfect for employee profiles.
    # -------------------------------------------------------------------
    
    # Check Memory Bank for dietary preferences. Fallback to default if empty.
    dietary = ctx.state.get("team_dietary_preferences")
    if not dietary:
        dietary = ["Gluten-Free", "Vegetarian"] # Mocking Alice and Charlie's preferences
        ctx.state["team_dietary_preferences"] = dietary

    # Check calendar free/busy times via Calendar API Tool
    calendar_json = get_calendar_availability(node_input.attendees)
    
    # Simulate schedule logic: analyzing busy slots to propose lunch
    # In a real solution, the agent parses the JSON and outputs the ideal slot.
    return TeamPreferences(
        dietary_needs=dietary,
        suggested_time="12:00 PM - 01:30 PM (90-minute slot available)"
    )


# Merge Phase: Fanning in parallel branches
join_phase = JoinNode(name="merge_planning_phase")


@node
def plan_catering(ctx: Context, node_input: dict) -> CateringDraft:
    """Node that matches dietary needs and selected calendar window against menu options."""
    
    # Access merged inputs fanned-in by the JoinNode
    agenda = node_input["agenda_agent"]["agenda_markdown"]
    preferences = node_input["get_preferences"]
    
    # Search catering database via tool
    # In Exercise 2/3, this endpoint is fronted by the luncher-mcp server
    menu_data = search_catering(cuisine="Healthy")
    
    # Match items complying with budget caps ($20/person) and dietary restrictions
    return CateringDraft(
        restaurant="Vibrant Salad Bar",
        menu_items=["Gluten-free Falafel bowl", "Vegetarian Quinoa salad"],
        total_cost=27.49
    )


async def hitl_approval(ctx: Context, node_input: CateringDraft):
    """Human-in-the-loop Node that requests coordinator approval before committing orders."""
    
    if not ctx.resume_inputs:
        # Halt execution and generate a RequestInput event to wait for user interaction
        yield RequestInput(
            interrupt_id="catering_order_approval",
            message=(
                f"📋 PROPOSED MEETING & CATERING DRAFT:\n"
                f"- Selected Restaurant: {node_input.restaurant}\n"
                f"- Items: {', '.join(node_input.menu_items)}\n"
                f"- Total Cost: ${node_input.total_cost:.2f}\n\n"
                f"Please reply with 'approve' or 'reject' to proceed."
            )
        )
        return
    
    # Process user response on resume
    user_response = ctx.resume_inputs["catering_order_approval"]
    if "approve" in user_response.lower():
        yield Event(output=node_input, route="approved")
    else:
        yield Event(output=node_input, route="rejected")


@node
def submit_order_node(ctx: Context, node_input: CateringDraft) -> str:
    """FunctionNode that submits the finalized order to the mock Luncher backend."""
    order_receipt = submit_catering_order(
        restaurant=node_input.restaurant,
        items=node_input.menu_items,
        total_cost=node_input.total_cost
    )
    return order_receipt


# ==========================================
# 5. Define Graph Workflow Edges
# ==========================================

luncher_workflow = Workflow(
    name="luncher_meeting_workflow",
    input_schema=MeetingRequest,
    edges=[
        # Parallel Fan-Out: Start parallel discovery tasks
        (START, agenda_agent),
        (START, get_preferences),
        
        # Parallel Fan-In: Merge results once both are finished
        ((agenda_agent, get_preferences), join_phase),
        
        # Sequential Processing: Draft catering based on meeting outline & preferences
        (join_phase, plan_catering),
        
        # Human Gate: Pause and get user confirmation
        (plan_catering, hitl_approval),
        
        # Conditional Edge Routing
        (hitl_approval, {"approved": submit_order_node}),
    ]
)


# ==========================================
# 6. Instantiate App Container
# ==========================================

root_agent = luncher_workflow

app = App(
    root_agent=root_agent,
    name="luncher-agent",
    # Enable state checkpointing to allow resumes across restarts/approval halts
    resumability_config=ResumabilityConfig(is_resumable=True)
)
