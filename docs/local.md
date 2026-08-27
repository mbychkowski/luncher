# Running and testing Luncher locally
To test the multi-agent orchestration locally, start the two sub-agents in background terminals, then launch the primary orchestrator in interactive web playground mode (or CLI mode). All commands execute directly from the repository root.

### Step 1: Start the Sub-Agents

Open **2 separate terminal windows/tabs** to start the Strategy and Scheduling sub-agents from root:

Terminal 1 — Strategy Agent (port 8081):

```bash
uv --directory agents/strat_agent run main.py
```

Terminal 2 — Scheduling Agent (port 8082):

```bash
uv --directory agents/sched_agent run main.py
```

---

### Step 2: Run the Orchestrator

With the sub-agents running, open a **3rd terminal** and run the Luncher Orchestrator
from root, either through the ADK web UI or from the CLI.

#### Option A: ADK web UI (port 8080)

```bash
uv --directory agents/luncher_agent run main.py
```
1. Open the dev UI in your browser:

   ```
   http://localhost:8080
   ```

2. Enter prompts such as:

   ```
   Plan a team lunch meeting for next week that aligns with our corporate strategy.
   ```

3. Watch the orchestrator delegate tasks to the Strategy (Port 8081) and Scheduling (Port 8082) sub-agents in real time.

The orchestrator replies with an A2UI proposal card ending in a booking button:

<img src="docs/images/book-this-lunch-button.png" alt="Book this lunch" width="141">

> **Note:** that button does nothing in the ADK dev UI, which renders A2UI but never sends actions back to the agent. To book locally, confirm in chat instead — *"that works, book it"*. The button works in Gemini Enterprise, whose A2UI client dispatches the action.

> **Note:** use `main.py`, not `adk web app`. Both serve the same ADK dev UI, but `adk web` builds its own app via the ADK CLI and therefore skips `app/fast_api_app.py` — so the A2A endpoints, the agent card and `/feedback` would not be served.

#### Option B: CLI (`agents-cli run`)

One prompt, no browser — the orchestrator is not left running.

```bash
uv run agents-cli run agents/luncher_agent "Plan a team lunch meeting for next week"
```