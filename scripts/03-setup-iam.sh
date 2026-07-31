#!/bin/bash
set -euo pipefail

# Copyright 2026 Antigravity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

if [ ! -f .env ]; then
  echo "Error: .env file not found. Please run scripts/01-setup-env.sh first."
  exit 1
fi

# Source environment variables
# shellcheck source=/dev/null
source .env

GOOGLE_CLOUD_PROJECT_ID="${GOOGLE_CLOUD_PROJECT_ID:-}"

if [ -z "${GOOGLE_CLOUD_PROJECT_ID:-}" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT_ID is not set in .env."
  exit 1
fi

echo "Setting up GCP IAM service account permissions for project ${GOOGLE_CLOUD_PROJECT_ID}..."

PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT_ID" --format="value(projectNumber)")

# 1. Reasoning Engine Service Account
RE_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
echo "Binding explicit roles to Reasoning Engine SA: ${RE_SA}..."

RE_ROLES=(
    "aiplatform.user"                        # Agent Platform User
    "agentregistry.viewer"                   # Agent Registry API Viewer
    "run.invoker"                            # Cloud Run Invoker
    "aiplatform.reasoningEngineServiceAgent" # Gemini Enterprise Agent Platform (GEAP) Reasoning Engine Service Agent
)

for role in "${RE_ROLES[@]}"; do
  echo "  - Binding roles/${role}..."
  gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT_ID" \
    --member="serviceAccount:${RE_SA}" \
    --role "roles/${role}" \
    --condition=None >/dev/null 2>&1 || true
done

# 2. Compute Service Account (Cloud Run runtime)
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "Binding storage.admin, artifactregistry.admin, logging.logWriter & run.invoker to Compute SA: ${COMPUTE_SA}..."
COMPUTE_ROLES=(
    "storage.admin"
    "artifactregistry.admin"
    "logging.logWriter"
    "run.invoker"
)

for role in "${COMPUTE_ROLES[@]}"; do
  echo "  - Binding roles/${role}..."
  gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role "roles/${role}" \
    --condition=None >/dev/null 2>&1 || true
done

# 3. Cloud Build Service Account
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Binding artifactregistry.admin to Cloud Build SA: ${CLOUDBUILD_SA}..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role "roles/artifactregistry.admin" \
  --condition=None >/dev/null 2>&1 || true

echo "IAM bindings successfully applied."
