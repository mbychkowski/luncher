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
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types

import shutil
import sys

# Load environment variables
load_dotenv()

try:
    from app.tools import (
        get_team_members,
        book_meeting,
        update_team_member_preferences,
    )
except ModuleNotFoundError:
    from .tools import (
        get_team_members,
        book_meeting,
        update_team_member_preferences,
    )

sched_retry_policy = types.HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503],
)

MODEL_LOCATION = os.getenv("GOOGLE_GENAI_LOCATION", "global")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
BQ_LOCATION = os.getenv("BIGQUERY_LOCATION", "US")

# BigQuery MCP Toolset Configuration
env_cmd = os.getenv("BIGQUERY_MCP_COMMAND")
venv_cmd = os.path.join(os.path.dirname(sys.executable), "bigquery-mcp")
bigquery_mcp_command = (
    env_cmd
    or shutil.which("bigquery-mcp")
    or (venv_cmd if os.path.exists(venv_cmd) else "bigquery-mcp")
)

bigquery_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=bigquery_mcp_command,
            args=[
                "--project", PROJECT_ID,
                "--location", BQ_LOCATION,
                "--datasets", "catering",
            ],
        )
    )
)

root_agent = Agent(
    model=Gemini(
        model="gemini-3.5-flash",
        retry_options=sched_retry_policy,
        client_kwargs={"location": MODEL_LOCATION},
    ),
    name="scheduling_agent",
    description="Helps coordinate meeting times and catering food preferences across team members interactively using BigQuery MCP menu data.",
    instruction=(
        "You are the Meeting and Catering Coordinator Agent. Your job is to help coordinate a meeting "
        "time and a catering restaurant/item for the team.\n\n"
        "Your available tools:\n"
        "1. 'get_team_members' - Loads profiles, timezone, availability, dietary restrictions, and cuisine preferences.\n"
        "2. BigQuery MCP Tools ('run_query', 'get_table', 'list_tables_in_dataset') - Queries BigQuery for catering menu items in the 'catering.menu_items' table.\n"
        "3. 'book_meeting' - Finalizes and records the booked meeting when the user confirms.\n"
        "4. 'update_team_member_preferences' - Permanently updates a member's preferences/dietary constraints in the database.\n\n"
        "CRITICAL BEHAVIOR RULES:\n"
        "- STEP 1: On your first turn, always load team profiles with 'get_team_members' and query catering options from the BigQuery table 'catering.menu_items' using BigQuery MCP tools (e.g. 'run_query').\n"
        "- STEP 2: Find overlapping weekly availabilities among all members and cross-reference them with catering options that respect "
        "everyone's dietary restrictions (e.g., allergens and dietary_labels) and align with their cuisine/dietary preferences.\n"
        "- STEP 3 (INTERACTIVE PROPOSING): You must propose EXACTLY ONE optimal recommendation first. Keep it simple, clear, and "
        "conversational. Do NOT dump all possible options or overload the user. Ask clearly for confirmation (e.g., 'Does Monday 10:00-11:00 AM "
        "with Caprese Focaccia Panini work for the team?').\n"
        "- STEP 4 (BOOKING EXECUTION): Only call 'book_meeting' after the user explicitly accepts your proposal. Never auto-book without consent.\n"
        "- STEP 5 (REJECTION & ALTERNATIVES): If the user rejects your proposal, search your database/BigQuery for the next best slot or item, "
        "and present that as the next single recommendation.\n"
        "- STEP 6 (MEMORY WRITING): If the user mentions a shift in general/permanent preferences (e.g., 'Alice is vegan now', or 'Bob doesn't like Mexican "
        "anymore'), you MUST call 'update_team_member_preferences' immediately to record it. Then recalculate your recommendations based "
        "on this updated central database."
    ),
    tools=[
        get_team_members,
        bigquery_mcp_toolset,
        book_meeting,
        update_team_member_preferences,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

