# 🍔 Luncher

---

## 🏗️ Architecture

The deployment architecture ensures secure, modern, and best-practice patterns:

1. **Secure Auth via Workload Identity**: No long-lived GCP service account keys (`JSON` files) are stored in GitHub. We use keyless OpenID Connect (OIDC) through Google Cloud Workload Identity Pools.
2. **Automated Infrastructure (Terraform)**: GCS Remote backend stores our state securely. Terraform acts as the single source of truth, managing:
   - An Artifact Registry repository (`luncher-repo`) for our container images.
   - The Cloud Run service (`luncher-service`) with secure configurations.
   - Public IAM permissions to allow unauthenticated web visitors.
3. **Continuous Delivery (CI/CD)**:
   - Built on-demand using Google Cloud Build (which avoids having to expose Docker daemons in GitHub runners).
   - Deployed directly and securely to **Google Cloud Run** by passing the newly compiled container image tag straight into a `terraform apply` step.

---

## 🛠️ Technology Stack

- **Code & Pipeline Management**: GitHub Actions & GitHub CLI (`gh`)
- **Infrastructure as Code**: Terraform (`>= 1.6.0`)
- **Container Registry**: GCP Artifact Registry
- **Serverless Hosting**: Google Cloud Run
- **Container Compilation**: GCP Cloud Build
- **Application Logic**: Python FastAPI & Uvicorn (Google ADK)

---

## 🚀 Getting Started: Initializing Your Project

Follow these steps to instantiate your own copy of the project and deploy it to your Google Cloud environment.

### 📌 Prerequisites

Ensure you have the following tools installed and authenticated on your local machine (or use **Google Cloud Shell**, which comes with all of these pre-installed):

1. [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)
2. [GitHub CLI (gh)](https://github.com/cli/cli#installation)
3. [Terraform](https://www.terraform.io/downloads.html)
4. [uv Python Package Manager](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
5. [Google ADK CLI (`adk`)](https://google.github.io/adk/) (`uv tool install google-adk` or `pip install google-adk`)

---

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

---

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

---

### Step 3: Enable Google Cloud APIs (`02-init-api.sh`)

Enable all of the required Google Cloud API services in your target GCP project:

```bash
./scripts/02-init-api.sh
```

---

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

---

### Step 5: Grant IAM Permissions (`04-setup-iam.sh`)

Grant your newly created GitHub Actions Service Account the minimum-privilege IAM roles required to provision and manage network, storage, and serverless resources:

```bash
./scripts/04-setup-iam.sh
```

---

### Step 6: Create State Bucket & Configure tfvars (`05-setup-tf.sh`)

Create the Google Cloud Storage bucket used to store your Terraform remote state file securely, copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, and automatically inject your configured environment values:

```bash
./scripts/05-setup-tf.sh
```

---

## 🏗️ Deployment Walkthrough

Once your environment is configured, the rest of the deployment is managed entirely through **GitHub Actions** in your fork!

### 📡 Phase 1: Deploy Infrastructure

1. Navigate to the **Actions** tab of your forked GitHub repository.
2. Select the **Terraform Deployment** workflow from the sidebar.
3. Click the **Run workflow** dropdown and trigger the workflow on the `main` branch.
4. This workflow will authenticate via Workload Identity, initialize Terraform pointing to your secure GCS bucket, and provision:
   - An Artifact Registry Docker repository (`luncher-repo`).
   - A secure Google Cloud Run service (`luncher-service`) pre-initialized with a standard public hello-world placeholder image.
   - Fully open public IAM ingress bindings so the service is unauthenticated.

---

### 📦 Phase 2: Build & Deploy Application

Once your infrastructure is ready, you can build and deploy your customized Flask application:

1. In the **Actions** tab, select the **Continuous Delivery** workflow.
2. Click **Run workflow** and trigger the deployment.
3. This workflow will:
   - Authenticate to your GCP project.
   - Run a Cloud Build trigger inside GCP to securely compile and tag the Python container.
   - Push the container image to your Artifact Registry.
   - Execute a `terraform apply` step, passing the newly compiled container image path into your Terraform configurations, updating the Cloud Run container securely, and providing your live public URL!

---

<<<<<<< HEAD
## 🤖 Interacting with Deployed Agents

Once deployed to Cloud Run or Vertex AI Reasoning Engine, you can interact with the multi-agent orchestrator using the official Google ADK `agents-cli` tool or directly via A2A endpoints:

### 1. Interactive Terminal Chat (`adk` & `agents-cli`)

* **Run Agent Locally (`adk run`):**
  ```bash
  cd agents/luncher_agent && \
  uv run adk run . "Plan a team lunch meeting for next week"
  ```

* **Run Local Web UI Playground (`adk web`):**
  ```bash
  cd agents/luncher_agent && \
  uv run adk web .
  ```

* **Query Deployed Cloud Run Agent (`agents-cli run`):**
  ```bash
  cd agents/luncher_agent && \
  uv run agents-cli run --mode a2a \
    --url https://<YOUR_CLOUD_RUN_URL> \
    "Plan a team lunch meeting for next week"
  ```

---

### 2. A2A Protocol Endpoints

* **Agent Card Discovery URL:**  
  `https://<YOUR_CLOUD_RUN_URL>/.well-known/agent-card.json`

* **JSON-RPC Endpoint:**  
  `https://<YOUR_CLOUD_RUN_URL>`

### 3. Accessing the ADK Web UI & Authenticated Proxy (`gcloud run services proxy`)

* **Public Web Playground:**
  Open `https://<YOUR_CLOUD_RUN_URL>/dev-ui/` directly in your browser.

* **Authenticated Local Tunnel (`gcloud run services proxy`):**
  If IAM authentication or domain restrictions are enabled on Cloud Run, launch an authenticated proxy tunnel to pass Google credentials automatically.

  You can retrieve the exact proxy command for your deployment from Terraform:
  ```bash
  cd terraform && terraform output -raw proxy_command
  ```
  Or run `gcloud` directly:
  ```bash
  gcloud run services proxy luncher-service --region us-central1 --project YOUR_PROJECT_ID
  ```
  Then open `http://localhost:8080/dev-ui/` in your browser.
=======
## 🤖 Running agents locally

To test the multi-agent orchestration locally, you need to run all three agents concurrently from the repository root:

### 1. Start the Strategy Agent (Port 8080)
```bash
PORT=8080 uv run agents/strat_agent/main.py
```

### 2. Start the Scheduling Agent (Port 8081)
```bash
PORT=8081 uv run agents/sched_agent/main.py
```

### 3. Start the Orchestrator Agent Playground (Port 8082)
The orchestrator agent coordinates the system. Start its web-based playground using:
```bash
uv run adk web --port 8082 agents/luncher_agent
```

Once all three are running, open the Orchestrator playground in your browser at `http://localhost:8082` to interact with and test the agents!

For more detail on each individual agent, see their respective READMEs:
* [Orchestrator Agent README](file:///home/mbychkowski/Code/luncher/agents/luncher_agent/README.md)
* [Strategy Agent README](file:///home/mbychkowski/Code/luncher/agents/strat_agent/README.md)
* [Scheduling Agent README](file:///home/mbychkowski/Code/luncher/agents/sched_agent/README.md)
>>>>>>> 6377cc0 (docs: update local execution instructions for agents)


## 🧼 Cleanup

To avoid ongoing charges, you can easily tear down all of the resources deployed in Google Cloud:

1. Go to your GitHub Fork's **Actions** tab.
2. Select the **Terraform DESTROY** workflow.
3. Click **Run workflow** and run it to automatically delete all Artifact Registry resources, public IAM bindings, and active Cloud Run service deployments in a single step!
