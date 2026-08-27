# Setup

### 📌 Prerequisites

Ensure you have the following CLI tools installed on your system:
- **Google Cloud SDK (`gcloud`)**: [Install Guide](https://cloud.google.com/sdk/docs/install)
- **Google `agents-cli`**: Install via `pip install google-agents-cli` or `uv tool install google-agents-cli`
- **`uv` Package Manager**: [Install Guide](https://docs.astral.sh/uv/)

Authenticate `gcloud` before running the setup scripts. `--update-adc` writes
Application Default Credentials in the same pass, which is what the agents and
the Google client libraries use:
```bash
gcloud auth login --update-adc
```

---

### 🛠️ Project Setup

Run the following shell scripts in order from the repository root.

#### Step 1: Configure Environment Variables (`01-setup-env.sh`)
```bash
./scripts/01-setup-env.sh
```

* **Main Takeaway**: Checks CLI prerequisites (`gcloud`, `agents-cli`, `uv`), prompts for your GCP project credentials, configures `gcloud` defaults, and generates the root `.env` file.
* **Environment Variables Configured**:
  | Variable | Description | Default / Example |
  | :--- | :--- | :--- |
  | `GOOGLE_GENAI_USE_VERTEXAI` | Forces Google GenAI SDK to route via Gemini Enterprise Agent Platform (GEAP) rather than Google AI Studio | `"true"` |
  | `GOOGLE_CLOUD_PROJECT_ID` | Your target Google Cloud Project ID | `"your-gcp-project-id"` |
  | `GOOGLE_CLOUD_LOCATION` | Primary GCP deployment region (Cloud Run, Reasoning Engine) | `"us-central1"` |
  | `GOOGLE_GENAI_LOCATION` | Location for Vertex AI Gemini model inference API calls | `"global"` |
  | `GOOGLE_GENAI_MODEL` | Gemini model used by all agents | `"gemini-3.6-flash"` |
  | `BIGQUERY_LOCATION` | Location of the BigQuery `catering` dataset | `"US"` |

* **Optional Variables** (not prompted for):
  | Variable | Description | Example |
  | :--- | :--- | :--- |
  | `BIGQUERY_MCP_COMMAND` | BigQuery MCP server command used by `sched_agent` | `"$PWD/agents/sched_agent/scripts/mock-bigquery-mcp"` |
  | `STRATEGY_DOCS_BUCKET` | GCS bucket holding the strategy PDFs read by `strat_agent` | `"your-gcp-project-id-strategy-docs"` |
  | `LOG_LEVEL` | Verbosity of the orchestrator's own logs. `INFO` adds a line per A2A event naming the agent that authored it and whether it was withheld | `"WARNING"` |
  | `STRATEGY_AGENT_URL` | Agent card URL of `strat_agent`, used by the orchestrator over A2A | resolved at deploy time |
  | `SCHEDULING_AGENT_URL` | Agent card URL of `sched_agent`, used by the orchestrator over A2A | resolved at deploy time |
  | `GOOGLE_CLOUD_AGENT_ENGINE_ID` | Engine holding **this** agent's sessions and Memory Bank. Injected on Agent Runtime; must be set explicitly on Cloud Run | resolved at deploy time |

---

#### Step 2: Enable APIs and Provision Resources (`02-init-api.sh`)
```bash
./scripts/02-init-api.sh
```

* **Main Takeaway**: Enables the required Google Cloud APIs, creates the BigQuery
  `catering` dataset and loads the menu data, and creates the Agent Engine that
  holds the orchestrator's sessions and Memory Bank.
* **Enabled APIs Summary**:
  | API Service | Purpose |
  | :--- | :--- |
  | `aiplatform.googleapis.com` | Gemini Enterprise Agent Platform (GEAP) Agent Runtime & Reasoning Engines |
  | `run.googleapis.com` | Cloud Run serverless container hosting for agents |
  | `artifactregistry.googleapis.com` | Container image storage repository |
  | `cloudbuild.googleapis.com` | Cloud Build automated container image compilation |
  | `compute.googleapis.com` | Provides the default compute service account Cloud Run runs as |
  | `bigquery.googleapis.com` | The `catering` dataset queried over MCP by `sched_agent` |
  | `apphub.googleapis.com` | Backs the Dashboard tab on an Agent Platform deployment |
  | `iam.googleapis.com` | Identity and Access Management service |
  | `cloudresourcemanager.googleapis.com` | GCP Project metadata & policy management |
  | `storage.googleapis.com` | Google Cloud Storage buckets for PDF documents and artifacts |
  | `serviceusage.googleapis.com` | Service usage API management |
  | `servicecontrol.googleapis.com` | Control plane reporting for GCP services |

---

#### Step 3: Configure IAM Permissions (`03-setup-iam.sh`)
```bash
./scripts/03-setup-iam.sh
```

* **Main Takeaway**: Grants necessary project-level IAM roles to Google Cloud runtime service accounts so agents, container runtimes, and build pipelines can execute seamlessly.
* **Service Accounts & Granted IAM Roles**:

  ##### 1. Gemini Enterprise Agent Platform (GEAP) Reasoning Engine Service Agent
  `service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com`
  - **`roles/aiplatform.user`** (*Agent Platform User*): Allows Reasoning Engine to execute models and manage sessions.
  - **`roles/agentregistry.viewer`** (*Agent Registry API Viewer*): Allows agent card discovery across registered A2A sub-agents.
  - **`roles/run.invoker`** (*Cloud Run Invoker*): Allows Reasoning Engine to invoke sub-agents deployed on Cloud Run.
  - **`roles/aiplatform.reasoningEngineServiceAgent`** (*Gemini Enterprise Agent Platform Reasoning Engine Service Agent*): Standard Reasoning Engine operational role.

  ##### 2. Compute Service Account (Cloud Run Runtime)
  `${PROJECT_NUMBER}-compute@developer.gserviceaccount.com`
  - **`roles/storage.admin`** (*Storage Admin*): Access strategy document PDFs and GCS log artifacts.
  - **`roles/artifactregistry.admin`** (*Artifact Registry Admin*): Pull container images for Cloud Run.
  - **`roles/logging.logWriter`** (*Logs Writer*): Write agent trace logs and telemetry to Cloud Logging.
  - **`roles/run.invoker`** (*Cloud Run Invoker*): Allows Cloud Run agent instances to invoke peer A2A Cloud Run services.

  ##### 3. Cloud Build Service Account
  `${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com`
  - **`roles/artifactregistry.admin`** (*Artifact Registry Admin*): Push built container images to Artifact Registry.

---

