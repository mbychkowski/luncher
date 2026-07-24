# 🍔 Luncher

## 🏗️ Architecture

The deployment architecture ensures secure, modern, and best-practice patterns:

1. **Secure Auth via Workload Identity**: No long-lived GCP service account keys (`JSON` files) are stored in GitHub. We use keyless OpenID Connect (OIDC) through Google Cloud Workload Identity Pools.
2. **Automated Infrastructure (Terraform)**: GCS Remote backend stores our state securely. Terraform acts as the single source of truth, managing:
   - An Artifact Registry repository (`luncher-repo`) for our container images.
   - The Cloud Run service (`luncher-service`) with secure configurations.
   - Public IAM permissions to allow unauthenticated web visitors.
3. **Continuous Delivery (CI/CD)**:
   - Built on-demand using Google Cloud Build and pushed to Artifact Registry.
   - Deployed directly to **Google Cloud Run** via `gcloud run deploy` for fast, lightweight application updates without invoking Terraform.

## 🛠️ Technology Stack

- **Code & Pipeline Management**: GitHub Actions & GitHub CLI (`gh`)
- **Infrastructure as Code**: Terraform (`>= 1.6.0`)
- **Container Registry**: GCP Artifact Registry
- **Serverless Hosting**: Google Cloud Run
- **Container Compilation**: GCP Cloud Build
- **Application Logic**: Python FastAPI & Uvicorn (Google ADK)

## 🚀 Getting Started: Initializing Your Project

Follow these steps to instantiate your own copy of the project and deploy it to your Google Cloud environment.

### 📌 Prerequisites

Ensure you have the following tools installed and authenticated on your local machine (or use **Google Cloud Shell**, which comes with all of these pre-installed):

1. [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)
2. [GitHub CLI (gh)](https://github.com/cli/cli#installation)
3. [Terraform](https://www.terraform.io/downloads.html)
4. [uv Python Package Manager](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
5. [Google ADK CLI (`adk`)](https://google.github.io/adk/) (`uv tool install google-adk` or `pip install google-adk`)

### Step 1: Fork and Clone the Repository

1. **Fork** this repository to your own GitHub account or organization.
2. **Clone** your fork locally and navigate into the directory:

```bash
git clone https://github.com/YOUR-USERNAME-OR-ORG/luncher.git
cd luncher
```

3. **Authenticate** your command line tools:

```bash
# Authenticate gcloud CLI
gcloud auth login
gcloud auth application-default login

# Authenticate GitHub CLI (strongly recommended to auto-populate GH Actions variables)
gh auth login
```

### Step 2: Configure Environment Variables (`01-setup-env.sh`)

Initialize your local configuration by running the interactive setup script. This script will inspect your current active `gcloud` and `git` status to guess sensible defaults, prompt you for confirmation, and save them to a `.env` file.

```bash
./scripts/01-setup-env.sh
```

During this step, you will be prompted for:
- **GitHub owner/organization** (your GitHub username/org name)
- **GitHub repository name** (e.g. `luncher`)
- **GCP project ID** (the Google Cloud project you wish to deploy to)
- **GCP region** (defaults to `us-central1`)

### Step 3: Enable Google Cloud APIs (`02-init-api.sh`)

Enable all of the required Google Cloud API services in your target GCP project:

```bash
./scripts/02-init-api.sh
```

### Step 4: Setup Workload Identity & Service Account (`03-setup-github-actions.sh`)

This script creates a secure GCP service account, initializes a global Workload Identity Pool, configures an OIDC provider mapped specifically to your GitHub fork, and **automates the setting of GitHub Actions Repository Variables** using the `gh` CLI!

```bash
./scripts/03-setup-github-actions.sh
```

> [!NOTE]
> The setup scripts automatically configure `GCP_AUTHORIZED_DOMAIN` (defaults to `google.com`). If you need to update your authorized domain for Cloud Run in GitHub Actions, run:
> ```bash
> gh variable set GCP_AUTHORIZED_DOMAIN --body "your-domain.com"
> ```
> If your `gh` CLI is not authenticated, you can manually set the variables in your GitHub Repository settings (**Settings > Secrets and variables > Actions > Variables**).

### Step 5: Setup IAP OAuth Brand & Client (`03b-setup-iap.sh`)

Provision the Identity-Aware Proxy (IAP) OAuth Brand and OAuth Client ID/Secret under your user credentials, and automatically sync `GCP_IAP_CLIENT_ID` and `GCP_IAP_CLIENT_SECRET` to your GitHub Actions repository:

```bash
./scripts/03b-setup-iap.sh
```

### Step 6: Grant IAM Permissions (`04-setup-iam.sh`)

Grant your newly created GitHub Actions Service Account the minimum-privilege IAM roles required to provision and manage network, storage, IAP, and serverless resources:

```bash
./scripts/04-setup-iam.sh
```

### Step 7: Create State Bucket & Configure tfvars (`05-setup-tf.sh`)

Create the Google Cloud Storage bucket used to store your Terraform remote state file securely, copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, and automatically inject your configured environment values:

```bash
./scripts/05-setup-tf.sh
```

## 🏗️ Deployment Walkthrough

The Luncher multi-agent system can be deployed using **automated CI/CD via GitHub Actions** or **manually via the CLI**.

### 🧩 Agent Deployment Architecture

The Luncher platform supports two deployment models for its multi-agent orchestration:

1. **Consolidated Container Deployment (Default & Recommended)**
   - All three agents (`luncher_agent`, `strat_agent`, `sched_agent`) are packaged into a single container image via the repository [Dockerfile](file:///home/mbychkowski/Code/luncher/Dockerfile).
   - Deployed as a single service on **Google Cloud Run**.
   - `luncher_agent` dynamically imports and executes `strat_agent` and `sched_agent` in-process, minimizing latency and simplifying infrastructure management while still serving ADK Web UI and A2A endpoints.

2. **Distributed Microservices / Agent Runtime Deployment**
   - Each agent is deployed independently as a separate Cloud Run service or Vertex AI Agent Runtime instance.
   - Connections between orchestrator and sub-agents use the Agent-to-Agent (A2A) protocol over HTTP/HTTPS.
   - Configured by passing environment variables (`STRAT_AGENT_URL`, `SCHED_AGENT_URL`) to `luncher_agent`. If deploying to Vertex AI Agent Runtime, `luncher_agent` automatically discovers sub-agent endpoints by `display_name`.

---

### Option A: Automated Deployment via GitHub Actions (CI/CD)

Once your GCP environment and GitHub secrets/variables are initialized (Steps 1–7 above), deployment is managed via GitHub Actions in your fork:

#### Phase 1: Deploy Infrastructure
1. Navigate to the **Actions** tab of your forked GitHub repository.
2. Select the **Terraform Deployment** workflow from the sidebar.
3. Click **Run workflow** on the `main` branch.
4. This workflow authenticates via Workload Identity, initializes Terraform with GCS remote state, and provisions:
   - An Artifact Registry Docker repository (`luncher-repo`).
   - A Cloud Run service (`luncher-service`) initialized with a base container.
   - Strategy Cloud Storage bucket (`luncher-strategy-docs-${PROJECT_ID}`).
   - Necessary IAM bindings and service identities.

#### Phase 2: Build & Deploy ADK Agent Container
1. Select the **Continuous Delivery** workflow in the **Actions** tab.
2. Click **Run workflow** on the `main` branch.
3. This workflow:
   - Authenticates to GCP using Workload Identity.
   - Triggers Google Cloud Build to compile and tag the Python container from the repository root `Dockerfile`.
   - Pushes the image to Artifact Registry (`luncher-repo`).
   - Deploys the container update directly to `luncher-service` on Cloud Run via `gcloud run deploy`.

---

### Option B: Manual CLI Deployment

If you prefer deploying directly from your local terminal or Google Cloud Shell:

#### 1. Build and Push Container Image with Cloud Build
From the repository root:
```bash
# Source environment variables
source .env

# Submit build to Cloud Build
gcloud builds submit . \
  --tag "${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/luncher-repo/luncher:latest" \
  --region "${GCP_LOCATION}"
```

#### 2. Deploy Infrastructure & Container via Terraform
```bash
cd terraform
terraform init -backend-config="bucket=bkt-tf-state-${GCP_PROJECT_ID}-${GITHUB_REPO}"
terraform apply \
  -var "project_id=${GCP_PROJECT_ID}" \
  -var "region=${GCP_LOCATION}" \
  -var "image_url=${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/luncher-repo/luncher:latest"
```

#### Alternative: Direct Cloud Run Deployment (`gcloud run deploy`)
```bash
gcloud run deploy luncher-service \
  --image "${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/luncher-repo/luncher:latest" \
  --region "${GCP_LOCATION}" \
  --platform managed \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GCP_LOCATION},STRATEGY_DOCS_BUCKET=luncher-strategy-docs-${GCP_PROJECT_ID}"
```

#### Alternative: Google ADK CLI Deployment (`agents-cli deploy`)
You can also deploy directly using the official Google ADK CLI:
```bash
# Deploy to Google Cloud Run
agents-cli deploy \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_LOCATION}" \
  --service-name luncher-service \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},STRATEGY_DOCS_BUCKET=luncher-strategy-docs-${GCP_PROJECT_ID}" \
  --no-confirm-project

# Or deploy to Vertex AI Agent Runtime
agents-cli deploy \
  --deployment-target agent_runtime \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_LOCATION}" \
  --service-name luncher-service \
  --no-confirm-project
```

## 🤖 Interacting with Deployed Agents

Once deployed to Cloud Run or Vertex AI Reasoning Engine, you can interact with the multi-agent orchestrator using the official Google ADK `agents-cli` tool or directly via A2A endpoints:

### 1. Interactive Terminal Chat (`adk` & `agents-cli`)

### 1. Connecting via ADK `agents-cli`

Execute remote calls or stream chat directly to your deployed service:

```bash
# Set your active deployment target URL
export AGENT_SERVICE_URL="https://<YOUR_CLOUD_RUN_URL>"

# Run interactive CLI session against deployed agents
agents-cli chat --url $AGENT_SERVICE_URL
```

### 2. A2A Protocol Endpoints

* **Agent Card Discovery URL:**
  `https://<YOUR_CLOUD_RUN_URL>/.well-known/agent-card.json`

* **JSON-RPC Endpoint:**
  `https://<YOUR_CLOUD_RUN_URL>`

### 3. Accessing the ADK Web UI & Authenticated Proxy (`gcloud run services proxy`)

When `AUTHORIZED_DOMAIN` restriction is enabled on Cloud Run, direct browser access will return `403 Forbidden`. You can use Google Cloud's built-in authenticated proxy to securely open the Web UI locally without making the service public:

```bash
gcloud run services proxy luncher-service --region us-central1 --project YOUR_PROJECT_ID
```

Then open `http://localhost:8080/dev-ui/` in your browser.

## 🔧 Manual Access & Quota Configuration (`gcloud`)

### Managing Cloud Run Invoker Permissions (Manual `gcloud`)
By default, the Cloud Run service is deployed without public unauthenticated invoker permissions.

* **To grant invoker access to a specific domain or user via `gcloud`:**
  ```bash
  gcloud run services add-iam-policy-binding luncher-service \
    --region us-central1 \
    --member="domain:yourcompany.com" \
    --role="roles/run.invoker"
  ```
* **To access the service securely without modifying IAM policies:**
  ```bash
  gcloud run services proxy luncher-service --region us-central1 --project YOUR_PROJECT_ID
  ```
  Then open `http://localhost:8080/dev-ui/` in your browser.

### Requesting Higher Gemini Quotas (Manual `gcloud`)
Default Vertex AI Gemini API rate limits are sufficient for development and testing. If you need higher throughput for production workloads, you can request a quota preference via `gcloud`:
```bash
gcloud services enable cloudquotas.googleapis.com
gcloud quotas preferences create \
  --service="aiplatform.googleapis.com" \
  --quota-id="GenerateContentRequestsPerMinutePerProjectPerRegionPerBaseModel" \
  --preferred-value=300 \
  --contact-email="your-email@example.com" \
  --dimensions="region=us-central1,base_model=gemini-2.5-flash"
```

## 🤖 Running agents locally

To test the multi-agent orchestration locally, you need to run all three agents concurrently from the repository root:

```bash
# Terminal 1: Run Strategy Agent
uv run -m agents.strat_agent.agent

# Terminal 2: Run Scheduling Agent
uv run -m agents.sched_agent.agent

# Terminal 3: Run Orchestrator Agent (Main entry point)
uv run -m agents.luncher_agent.agent
```

For more detail on each individual agent, see their respective READMEs:
* [Orchestrator Agent README](file:///home/mbychkowski/Code/luncher/agents/luncher_agent/README.md)
* [Strategy Agent README](file:///home/mbychkowski/Code/luncher/agents/strat_agent/README.md)
* [Scheduling Agent README](file:///home/mbychkowski/Code/luncher/agents/sched_agent/README.md)

## 🧼 Cleanup

To avoid ongoing charges, you can easily tear down all of the resources deployed in Google Cloud:

1. Go to your GitHub Fork's **Actions** tab.
2. Select the **Terraform DESTROY** workflow.
3. Click **Run workflow** and run it to automatically delete all Artifact Registry resources, public IAM bindings, and active Cloud Run service deployments in a single step!
