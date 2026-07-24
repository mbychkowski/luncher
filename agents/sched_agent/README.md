# 📅 Meeting Scheduling Agent

An agentic application built using the Google Agent Development Kit (ADK) that interactively schedules team meetings and coordinates catering options based on overlapping weekly schedules, dietary restrictions, and preferred cuisines.

The agent features a **central long-term memory write-back pattern**, allowing it to permanently update team member preferences (simulating the Enterprise Memory Bank or traditional database patterns) and remember them across future conversations.

It is exposed via the **Agent-to-Agent (A2A)** protocol, making it ready for multi-agent collaboration and fully compatible with Google's managed **Agent Runtime**.

---

## 🏗️ Architecture & Mock Databases

To ensure reliable, deterministic, and testable behavior, the agent uses three structured JSON files inside the `data/` directory:

1. **`data/team_members.json`**: Holds profiles, preferred times, dietary restrictions, cuisine interests, and weekly schedule availabilities.
2. **`data/catering_options.json`**: Lists local catering options, ratings, and dietary compatibility (Vegetarian, Gluten-Free, Halal, etc.).
3. **`data/booked_meetings.json`**: Holds record of successfully scheduled and confirmed meetings.

---

## 🛠️ Specialized Tools

The agent is equipped with four custom python tools:
- `get_team_members()`: Retrieves team member schedules and profiles.
- `get_catering_options()`: Retrieves catering options.
- `book_meeting(time_slot, restaurant, reason)`: Records a finalized meeting when the user confirms.
- `update_team_member_preferences(name, preferred_time_of_day, dietary_restrictions, cuisine_preferences)`: Updates the permanent `team_members.json` database dynamically when users express changing preferences.

---

## 🚀 Local Development & Execution

To initialize the virtual environment, synchronize dependencies, and start the agent:

### 1. Synchronize the Workspace
From the repository root, run:
```bash
uv sync
```

### 2. Start the Agent A2A Server
Run the agent server:
```bash
PORT=8081 uv run agents/sched_agent/main.py
```
The server will boot up, expose its schema, and list on `0.0.0.0:8081`. You can retrieve its **Agent Card** at:
`http://localhost:8081/.well-known/agent-card.json`

---

## 🤖 Testing via the Agents CLI Playground

The easiest way to test this agent interactively is using the workspace's playground. 

1. From the repo root, run:
   ```bash
   uv run adk web agents/sched_agent
   ```
2. Open the playground in your browser and try interacting with it!

### Example Test Scenarios to Try:

#### Scenario A: The Standard Golden Flow
- **Prompt:** *"Hi, please help me schedule a meeting for Alice, Bob, and Charlie."*
- **Expected Agent Action:** The agent loads the database, calculates that the only joint free slot is **Monday 10:00 - 11:00 AM**, and identifies that **Fiesta Tacos** perfectly fits Alice's vegetarian and Charlie's gluten-free requirements while matching everyone's cuisine preferences.
- **Agent Response:** It should propose *exactly one option* (e.g., *"I've found a perfect slot on Monday from 10:00 to 11:00 AM with catering from Fiesta Tacos..."*) and ask for confirmation.
- **Prompt:** *"That works perfectly, let's book it!"*
- **Expected Agent Action:** The agent calls `book_meeting`, saves the record in `data/booked_meetings.json`, and returns the booking ID.

#### Scenario B: Interactively Updating Long-term Memory
- **Prompt:** *"Help schedule a meeting for the team. By the way, Alice is now vegan instead of vegetarian, so make sure to update her profile."*
- **Expected Agent Action:** The agent identifies a permanent shift in preferences, invokes the `update_team_member_preferences` tool (updating Alice's dietary restrictions to `["Vegan"]` in `data/team_members.json`), and then recalculates.
- **Expected Agent Response:** It confirms the permanent update to Alice's profile, and suggests a catering option that fits a Vegan diet (e.g., **Green Garden**).
- **Subsequent Run Check:** View `data/team_members.json` to verify Alice's record was permanently updated!

---

## ☁️ Deployment

`sched_agent` can be deployed either as part of the consolidated `luncher` container or as an independent microservice:

### 1. Standalone Deployment to Cloud Run
To deploy `sched_agent` as an independent Cloud Run microservice:

```bash
gcloud run deploy sched-agent \
  --source . \
  --command "uvicorn" \
  --args "agents.sched_agent.main:a2a_app,--host,0.0.0.0,--port,8080" \
  --region us-central1 \
  --project YOUR_PROJECT_ID
```

### 2. Standalone Deployment via ADK CLI (`agents-cli deploy`)
```bash
agents-cli deploy \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --service-name sched-agent \
  --no-confirm-project
```

Once deployed, copy the service URL and pass it to `luncher_agent` via `SCHED_AGENT_URL`.

