# 🛰️ Luncher Orchestrator Agent

The centralized Orchestrator Agent (the cognitive frontend) for the Luncher platform. It coordinates with both `strat_agent` (Strategy Agent) and `sched_agent` (Scheduling Agent) using the Google Agent Development Kit (ADK) and the Agent-to-Agent (A2A) protocol.

---

## 🏗️ Architecture

The Orchestrator acts as the "cognitive frontend" or user gateway, delegating specialized sub-tasks to the backend agents:
1. **`strat_agent`**: Queried via A2A to extract current corporate strategic goals (e.g., launching *OmniChef* or strategic business constraints).
2. **`sched_agent`**: Queried via A2A to perform team schedule checks, manage preferences, and book catering.

---

## ☁️ Deployment Target

`luncher_agent` deploys to **Cloud Run** (`deployment_target: cloud_run`). It renders
A2UI, which a client may only interpret once the server echoes the request's
`X-A2A-Extensions` header — and Agent Runtime's `/api/` passthrough replaces response
headers wholesale, so the echo never reaches the caller. The two sub-agents emit no
A2UI and deploy to Agent Runtime. See the root `README.md` for the deployment sequence.

---

## 🚀 Local Development & Execution

Start each agent in its own terminal, from the repository root. Every `main.py`
defaults to the port shown, so no `PORT` override is needed.

### 1. Start Strategy Agent (port 8081)
```bash
uv --directory agents/strat_agent run main.py
```

### 2. Start Scheduling Agent (port 8082)
```bash
uv --directory agents/sched_agent run main.py
```

### 3. Start Orchestrator Agent (port 8080)
```bash
uv --directory agents/luncher_agent run main.py
```

Then open the dev UI:

```
http://localhost:8080
```

then prompt the orchestrator, e.g.

```
Plan a team lunch meeting for next week that aligns with our corporate strategy.
```

The orchestrator replies with an A2UI proposal card ending in a booking button:

<img src="../../docs/images/book-this-lunch-button.png" alt="Book this lunch" width="141">

> **Note:** that button does nothing in the ADK dev UI, which renders A2UI but never
> sends actions back to the agent. To book locally, confirm in chat instead — *"that
> works, book it"*. The button works in Gemini Enterprise, whose A2UI client
> dispatches the action.

> **Note:** use `main.py`, not `adk web`. Both serve the same ADK dev UI, but `adk web`
> builds its own app via the ADK CLI and therefore skips `app/fast_api_app.py` — so the
> A2A endpoints, the agent card and `/feedback` would not be served.
