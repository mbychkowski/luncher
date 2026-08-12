# 📅 Meeting Scheduling Agent

An agentic application built using the Google Agent Development Kit (ADK) that interactively schedules team meetings based on overlapping weekly schedules and timezones. Food preferences and memories are maintained centrally by `luncher_agent`.

It is exposed via the **Agent-to-Agent (A2A)** protocol, making it ready for multi-agent collaboration and fully compatible with Google's managed **Agent Runtime**.

---


## 🏗️ Architecture & Database Integrations

1. **Local Development (Mock Databases)**:
   - **`data/team_members.json`**: Holds profiles, timezones, and weekly schedule availabilities.
   - **`data/booked_meetings.json`**: Holds record of successfully scheduled and confirmed meetings.

2. **BigQuery Integration via Model Context Protocol (MCP)**:
   - In production, `sched_agent` integrates a **BigQuery MCP Server** connector (`bigquery_dataset.catering_options`). This allows querying live catering vendor menus and compatibility in BigQuery via MCP standard tools.


---

## 🛠️ Specialized Tools

The agent is equipped with custom python tools:
- `get_team_members()`: Retrieves team member schedules, timezones, and availability.
- `book_meeting(time_slot, restaurant, reason)`: Records a finalized meeting when the user confirms.

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

### Example Test Scenario:

- **Prompt:** *"Hi, please help me schedule a meeting for Alice, Bob, and Charlie."*
- **Expected Agent Action:** The agent loads the database, calculates joint free slots based on member availabilities, and proposes an optimal slot.
- **Prompt:** *"That works perfectly, let's book it!"*
- **Expected Agent Action:** The agent calls `book_meeting`, saves the record in `data/booked_meetings.json`, and returns the booking ID.

