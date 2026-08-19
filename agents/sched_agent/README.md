# 📅 Meeting Scheduling Agent

An agentic application built using the Google Agent Development Kit (ADK) that interactively schedules team meetings based on overlapping weekly schedules and timezones, and records confirmed bookings in a shared team calendar. Per-user food preferences and conversational memories are maintained centrally by `luncher_agent`.

It is exposed via the **Agent-to-Agent (A2A)** protocol, making it ready for multi-agent collaboration and fully compatible with Google's managed **Agent Runtime**.

---


## 🏗️ Architecture & Database Integrations

1. **Team profiles**:
   - **`app/data/team_members.json`**: Holds profiles, timezones, and weekly schedule
     availabilities. Override the directory with `DATA_DIR`.

2. **Bookings in Agent Platform Memory Bank**:
   - Confirmed meetings are written to the Memory Bank of the engine named by
     `GOOGLE_CLOUD_AGENT_ENGINE_ID`, under a constant team scope
     (`app_name=sched_agent`, `user_id=team`) so every caller sees one shared
     calendar. `app/bookings.py` calls the Memory Bank API directly.
   - This is why the agent deploys to **Agent Runtime**: the runtime injects
     `GOOGLE_CLOUD_AGENT_ENGINE_ID`, so the host *is* the memory host.

3. **BigQuery Integration via Model Context Protocol (MCP)**:
   - `sched_agent` spawns a **BigQuery MCP Server** over stdio and queries live
     catering menus from the `catering.menu_items` table via standard MCP tools
     (`run_query`, `get_table`, `list_tables_in_dataset`).
   - For offline work, point `BIGQUERY_MCP_COMMAND` at
     `agents/sched_agent/scripts/mock-bigquery-mcp`, which serves
     `data/catering/catering_menu.json` from an in-process DuckDB so
     `catering.menu_items` resolves unchanged.

---

## 🛠️ Specialized Tools

The agent is equipped with custom python tools:
- `get_team_members()`: Retrieves team member schedules, timezones, and availability.
- `book_meeting(time_slot, restaurant, reason)`: Records a finalized meeting when the user confirms.
- `get_bookings()`: Lists the team's existing bookings so the agent does not propose a slot that is already taken.

---

## 🚀 Local Development & Execution

Run from the repository root. `uv` synchronizes the agent's dependencies and starts
the A2A server:

```bash
uv --directory agents/sched_agent run main.py
```

The server boots, exposes its schema, and listens on `0.0.0.0:8082`. Each agent
carries its own `pyproject.toml`, so `--directory` is what selects the environment —
a bare `uv run` or `uv sync` from the root fails with `No pyproject.toml found`.

Retrieve its **Agent Card** at:

```
http://localhost:8082/a2a/app/.well-known/agent-card.json
```

---

## 🤖 Testing Interactively

`main.py` serves the ADK dev UI alongside the A2A endpoints. With the agent running,
open:

```
http://localhost:8082
```

> **Note:** use `main.py`, not `adk web`. Both serve the same ADK dev UI, but `adk web`
> builds its own app via the ADK CLI and therefore skips `app/fast_api_app.py` — so the
> A2A endpoints, the agent card and `/feedback` would not be served.

### Example Test Scenario:

- **Prompt:** *"Hi, please help me schedule a meeting for Alice, Bob, and Charlie."*
- **Expected Agent Action:** The agent loads the database, calculates joint free slots based on member availabilities, and proposes an optimal slot.
- **Prompt:** *"That works perfectly, let's book it!"*
- **Expected Agent Action:** The agent calls `book_meeting`, writes the record to the team-scoped Memory Bank, and returns the booking ID. Ask again in a fresh conversation and `get_bookings` returns the same slot.

