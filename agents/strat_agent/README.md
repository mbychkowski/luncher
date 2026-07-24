# 🧠 Corporate Strategy Agent

An agentic application built using the Google Agent Development Kit (ADK) that inspects corporate documents (PDFs) and synthesizes the implied corporate strategy into a terse, high-quality statement using bulleted assertions.

The agent is exposed via the open **Agent-to-Agent (A2A)** protocol, allowing other distributed agents to call, delegate, and collaborate with it.

---

## 🛠️ Configuration

The agent is dynamically self-configuring and switches its document source based on environment variables:

1. **Local Development (Default)**:
   Reads `.pdf` files from the local directory `assets/docs/`.
2. **Production (Google Cloud)**:
   If `STRATEGY_DOCS_BUCKET` is specified, the agent connects via the Google Cloud SDK client to read strategy PDFs directly from the GCS bucket.

### `.env` Parameters

Create or update the `.env` file at the repository root:

```env
# (Optional) GCS bucket for production document storage
STRATEGY_DOCS_BUCKET="your-gcs-bucket-name"

# Port to listen on (Agent Runtime automatically injects this)
PORT=8080

# Gemini API Key or GCP Credentials
GEMINI_API_KEY="your_gemini_api_key_here"
```

---

## 🚀 Execution & Local Testing

### Standard Execution

To start the agent's server, run `uv run` from the repository root. `uv` will automatically synchronize the workspace dependencies and run the agent service:

```bash
uv run agents/strat_agent/main.py
```

---

### Alternative: Manual Workspace Sync

If you prefer to manually synchronize the workspace environment first:

1. Synchronize the workspace dependencies:
   ```bash
   uv sync
   ```

2. Run the A2A Server:
   ```bash
   uv run agents/strat_agent/main.py
   ```

The server will start up and listen on `0.0.0.0:8080` (or the configured `PORT`).

---

## 🛰️ A2A Integration

When running, the agent automatically advertises its capabilities via an **Agent Card** at:
- `http://localhost:8080/.well-known/agent-card.json`

Other agents can call this agent programmatically using the ADK's `RemoteA2aAgent` class:

```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

# Instantiate remote A2A connection
strategy_agent = RemoteA2aAgent(
    name="strategy_agent",
    description="Corporate Strategy Synthesizer",
    agent_card="http://localhost:8080/.well-known/agent-card.json"
)

# Invoke the strategy analysis
result = strategy_agent.call("Please analyze the strategy documents and return a summary.")
print(result)
```

---

## ☁️ Deployment

`strat_agent` can be deployed either as part of the primary `luncher` container image or as an independent microservice on **Google Cloud Run** or **Vertex AI Agent Runtime**.

### 1. Standalone Deployment to Cloud Run (`gcloud`)

To deploy `strat_agent` as an independent Cloud Run microservice:

```bash
gcloud run deploy strat-agent \
  --source . \
  --command "uvicorn" \
  --args "agents.strat_agent.main:a2a_app,--host,0.0.0.0,--port,8080" \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --set-env-vars "STRATEGY_DOCS_BUCKET=luncher-strategy-docs-YOUR_PROJECT_ID,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID"
```

Ensure the Cloud Run Service Account has `roles/storage.objectViewer` on your strategy docs Cloud Storage bucket.

### 2. Standalone Deployment via ADK CLI (`agents-cli deploy`)

Deploy to Cloud Run:
```bash
agents-cli deploy \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --service-name strat-agent \
  --update-env-vars "STRATEGY_DOCS_BUCKET=luncher-strategy-docs-YOUR_PROJECT_ID,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID" \
  --no-confirm-project
```

Or deploy to **Vertex AI Agent Runtime**:
```bash
agents-cli deploy \
  --deployment-target agent_runtime \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --service-name strat-agent \
  --update-env-vars "STRATEGY_DOCS_BUCKET=luncher-strategy-docs-YOUR_PROJECT_ID" \
  --no-confirm-project
```

Once deployed, copy the service URL and pass it to `luncher_agent` via `STRAT_AGENT_URL` (or rely on Vertex AI dynamic discovery by `display_name`).

