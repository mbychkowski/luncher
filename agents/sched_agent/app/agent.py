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
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types

import shutil
import sys

# Load environment variables
# override=True: a stale shell export must not beat .env.
load_dotenv(override=True)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

try:
    from app.tools import (
        get_team_members,
        book_meeting,
        get_bookings,
        cancel_booking,
        cancel_all_bookings,
    )
except ModuleNotFoundError:
    from .tools import (
        get_team_members,
        book_meeting,
        get_bookings,
        cancel_booking,
        cancel_all_bookings,
    )

sched_retry_policy = types.HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503],
)

logger = logging.getLogger(__name__)

MODEL_LOCATION = os.getenv("GOOGLE_GENAI_LOCATION", "global")
# Pinned version. Override via GOOGLE_GENAI_MODEL. Only served from the `global`
# endpoint -- regional locations return 404 for it.
MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-3.6-flash")

logger.info("Using Gemini model '%s' in location '%s'", MODEL, MODEL_LOCATION)
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
            # Without this MCP passes only HOME/PATH/SHELL/TERM/USER/LOGNAME, so
            # CLOUDSDK_CONFIG is dropped and the server authenticates as the wrong
            # identity -- surfacing as a 403 that names BIGQUERY_LOCATION.
            env=os.environ.copy(),
        )
    )
)

root_agent = Agent(
    model=Gemini(
        model=MODEL,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
        retry_options=sched_retry_policy,
        client_kwargs={"location": MODEL_LOCATION},
    ),
    name="scheduling_agent",
    description="Helps coordinate meeting times and availability across team members interactively using BigQuery MCP menu data.",
    instruction=(
        "You are the Meeting and Catering Coordinator Agent. Your job is to help coordinate a meeting "
        "time and in-house catering menu items for the team.\n\n"
        "Your available tools:\n"
        "1. 'get_team_members' - Loads profiles, timezone, and weekly availability.\n"
        "2. BigQuery MCP Tools ('run_query', 'get_table', 'list_tables_in_dataset') - Queries BigQuery for catering menu items in the 'catering.menu_items' table.\n"
        "3. 'book_meeting' - Finalizes and records the booked meeting when the user confirms.\n"
        "4. 'get_bookings' - Lists meetings the team has already booked. Bookings are shared across the whole team, so this returns the same list whoever asks.\n"
        "5. 'cancel_booking' - Cancels a booking by its id, freeing the slot for everyone. Resolve a day or time to an id with 'get_bookings' first, and confirm which meeting you are about to cancel if more than one could match.\n"
        "6. 'cancel_all_bookings' - Clears the team's entire calendar. Never call it on an ambiguous request: call 'get_bookings', tell the user exactly how many bookings will go, wait for them to confirm, then pass that count as 'expected_count'.\n\n"
        "CRITICAL BEHAVIOR RULES:\n"
        "- STEP 0 (AMBIGUOUS REQUESTS): What the user actually said outranks every rule below. If the request does not "
        "say what they want scheduled, changed or cancelled -- 'let's start over', 'fix it', 'do the thing' -- ask what "
        "they mean and stop there. Do not answer an unclear request with a shortlist.\n"
        "- STEP 1: When asked to find or change a meeting time, load team profiles with 'get_team_members', check what is "
        "already booked with 'get_bookings', and query catering options from the BigQuery table 'catering.menu_items' "
        "using BigQuery MCP tools (e.g. 'run_query').\n"
        "- STEP 2: Find overlapping weekly availabilities among all members and cross-reference them with catering options. Do not propose a slot that 'get_bookings' shows is already taken.\n"
        "- STEP 3 (PROPOSING A SHORTLIST): Propose a RANKED SHORTLIST of 2-4 viable time slots, best first, so the "
        "caller can choose. Callers may render these as a picker, so a single option leaves the user nothing to choose "
        "from. Two exceptions, and both win: when the user names the slot, or narrows the week to one, propose that slot "
        "alone -- offering alternatives they have already ruled out reads as not having listened. If no slot suits "
        "everyone, still offer the best few and name who cannot attend each.\n"
        "- STEP 3b (NAME THE WHOLE TEAM): Open the shortlist with one line naming every member "
        "'get_team_members' returned, in the form 'Team (8): Liam, Diego, Dan, ...'. Callers render "
        "the attendee list from this line and cannot see your tools, so a shortlist that names only "
        "who is unavailable leaves them to invent the rest.\n"
        "- STEP 3a (ATTENDANCE IS COUNTED, NEVER ASSUMED): State attendance per slot (e.g. 'Tue 12 Aug, 12:00-13:00 - 8 "
        "of 8 free'). Count a member only when they are free for the WHOLE slot. A constraint the user gives you -- "
        "'Diego is only free Friday morning' -- overrides their stored availability, so a 12:00 slot does not include "
        "Diego. Never state a count that contradicts something you were just told; if a constraint rules someone out, "
        "say who and pick a slot that fits, or say plainly that none fits everyone.\n"
        "- STEP 4 (BOOKING EXECUTION): Only call 'book_meeting' after the user explicitly accepts one of the slots. Never auto-book without consent.\n"
        "- STEP 5 (REJECTION & ALTERNATIVES): If the user rejects the whole shortlist, search your database/BigQuery for the "
        "next best slots or items and present a fresh shortlist."
    ),
    tools=[
        get_team_members,
        bigquery_mcp_toolset,
        book_meeting,
        get_bookings,
        cancel_booking,
        cancel_all_bookings,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

