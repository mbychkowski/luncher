# 🛰️ Luncher Orchestrator Agent

The centralized Orchestrator Agent (the cognitive frontend) for the Luncher platform. It coordinates with both `strat_agent` (Strategy Agent) and `sched_agent` (Scheduling Agent) using the Google Agent Development Kit (ADK) and the Agent-to-Agent (A2A) protocol.

---

## 🏗️ Architecture

The Orchestrator acts as the "cognitive frontend" or user gateway, delegating specialized sub-tasks to the backend agents:
1. **`strat_agent`**: Queried via A2A to extract current corporate strategic goals (e.g., launching *OmniChef* or strategic business constraints).
2. **`sched_agent`**: Queried via A2A to perform team schedule checks, manage preferences, and book catering.

---

## 🚀 Local Development & Execution

To run the orchestrator and downstream agents locally:

### 1. Start Strategy Agent (Port 8080)
```bash
PORT=8080 uv run agents/strat_agent/main.py
```

### 2. Start Scheduling Agent (Port 8081)
```bash
PORT=8081 uv run agents/sched_agent/main.py
```

### 3. Start Orchestrator Agent (Port 8082)
```bash
uv run adk web --port 8082 agents/luncher_agent
```

---

## ☁️ Deployment

### 1. Consolidated Deployment (Google Cloud Run)

In production, `luncher_agent` is deployed to Google Cloud Run as the main entry point container using the repository root `Dockerfile`.

Because the repository `Dockerfile` copies all sub-agent packages into the container, `luncher_agent` loads `strat_agent` and `sched_agent` in-process by default, exposing both the A2A endpoint and the ADK Web UI on `PORT 8080`.

To deploy using `agents-cli`:

```bash
agents-cli deploy \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --service-name luncher-service \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,STRATEGY_DOCS_BUCKET=luncher-strategy-docs-YOUR_PROJECT_ID" \
  --no-confirm-project
```

### 2. Distributed Microservices Deployment (Remote A2A Connections)

If `strat_agent` and `sched_agent` are deployed as independent remote services (e.g. on separate Cloud Run instances or Vertex AI Agent Runtime), configure `luncher_agent` to route calls to them via environment variables:

```bash
export STRAT_AGENT_URL="https://strat-agent-service-url.run.app"
export SCHED_AGENT_URL="https://sched-agent-service-url.run.app"
```

When running on Vertex AI Agent Runtime with `GOOGLE_CLOUD_PROJECT` set, `luncher_agent` also supports dynamic discovery of reasoning engines matching display names `strat-agent` and `sched-agent`.

