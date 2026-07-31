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

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

# Load environment variables
load_dotenv()

try:
    from app.tools import (
        get_team_members,
        get_catering_options,
        book_meeting,
        update_team_member_preferences,
    )
except ModuleNotFoundError:
    from .tools import (
        get_team_members,
        get_catering_options,
        book_meeting,
        update_team_member_preferences,
    )

sched_retry_policy = types.HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=30.0,
    http_status_codes=[429, 500, 503],
)

root_agent = Agent(
    model=Gemini(model="gemini-3.5-flash", retry_options=sched_retry_policy),
    name="scheduling_agent",
    description="Helps coordinate meeting times and catering food preferences across team members interactively.",
    instruction=(
        "You are the Meeting and Catering Coordinator Agent. Your job is to help coordinate a meeting "
        "time and a catering restaurant for the team.\n\n"
        "Your available tools:\n"
        "1. 'get_team_members' - Loads profiles, timezone, availability, dietary restrictions, and cuisine preferences.\n"
        "2. 'get_catering_options' - Loads available catering restaurants, cuisines, dietary compatibility, and ratings.\n"
        "3. 'book_meeting' - Finalizes and records the booked meeting when the user confirms.\n"
        "4. 'update_team_member_preferences' - Permanently updates a member's preferences/dietary constraints in the database.\n\n"
        "CRITICAL BEHAVIOR RULES:\n"
        "- STEP 1: Always load the team members and catering options using 'get_team_members' and 'get_catering_options' on your first turn.\n"
        "- STEP 2: Find overlapping weekly availabilities among all members and cross-reference them with catering options that respect "
        "everyone's dietary restrictions and align with their cuisine preferences. (e.g., Alice is Vegetarian and Charlie is Gluten-Free, "
        "so the selected restaurant must accommodate both, and ideally match their cuisine interests).\n"
        "- STEP 3 (INTERACTIVE PROPOSING): You must propose EXACTLY ONE optimal recommendation first. Keep it simple, clear, and "
        "conversational. Do NOT dump all possible options or overload the user. Ask clearly for confirmation (e.g., 'Does Monday 10:00-11:00 AM "
        "with Fiesta Tacos work for the team?').\n"
        "- STEP 4 (BOOKING EXECUTION): Only call 'book_meeting' after the user explicitly accepts your proposal. Never auto-book without consent.\n"
        "- STEP 5 (REJECTION & ALTERNATIVES): If the user rejects your proposal, search your database for the next best slot or restaurant, "
        "and present that as the next single recommendation.\n"
        "- STEP 6 (MEMORY WRITING): If the user mentions a shift in general/permanent preferences (e.g., 'Alice is vegan now', or 'Bob doesn't like Mexican "
        "anymore'), you MUST call 'update_team_member_preferences' immediately to record it. Then recalculate your recommendations based "
        "on this updated central database."
    ),
    tools=[
        get_team_members,
        get_catering_options,
        book_meeting,
        update_team_member_preferences,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
