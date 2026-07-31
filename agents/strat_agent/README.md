# 🧠 Corporate Strategy Agent

An agentic application built using the Google Agent Development Kit (ADK) that inspects corporate documents (PDFs) and synthesizes the implied corporate strategy into a terse, high-quality statement using bulleted assertions.

The agent is exposed via the open **Agent-to-Agent (A2A)** protocol, allowing other distributed agents to call, delegate, and collaborate with it.


---

## 🏛️ Architecture & Document Storage

- **Local Development**: Reads strategy `.pdf` files from the local directory `agents/strat_agent/data/docs/`.
- **Google Cloud Storage (GCS) Integration**: In production deployments, `strat_agent` connects to a designated GCS Bucket (`gs://$GOOGLE_CLOUD_PROJECT_ID-strategy-docs/`) to dynamically retrieve corporate strategy PDF documents for automated indexing and RAG processing.

---

## 🛠️ Configuration

The agent is dynamically self-configuring and switches its document source based on environment variables:

1. **Local Development (Default)**:
   Reads `.pdf` files from the local directory `agents/strat_agent/data/docs/`.
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

## ☁️ Agent Runtime Deployment

The agent is fully compatible with **Agent Runtime**, Google's fully-managed platform for hosting AI agents. To deploy:

1. Containerize the application using standard Cloud Build.
2. Deploy to Agent Runtime with `PORT` mapping.
3. Configure the `STRATEGY_DOCS_BUCKET` env variable in your Deployment configuration.
4. Ensure the Agent Runtime Service Account has `roles/storage.objectViewer` permissions on your GCS bucket.
