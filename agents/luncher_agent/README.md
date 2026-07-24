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
