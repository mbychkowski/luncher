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

SA_EMAIL="${GCP_SA_GITHUB_ACTIONS}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Applying least-privilege IAM roles to GitHub Actions Service Account: ${SA_EMAIL}..."

# Project-level roles required for Cloud Run, GCLB Load Balancing, IAP, OAuth Brand, Cloud Endpoints, and Terraform
ROLES=(
    "artifactregistry.admin"
    "cloudbuild.builds.editor"
    "cloudquotas.admin"
    "compute.admin"
    "iap.admin"
    "logging.logWriter"
    "oauthconfig.editor"
    "resourcemanager.projectIamAdmin"
    "run.admin"
    "servicemanagement.admin"
    "serviceusage.serviceUsageConsumer"
    "storage.admin"
    "viewer"
)

for role in "${ROLES[@]}"; do
  echo "Binding project role roles/${role}..."
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role "roles/$role" \
    --condition=None >/dev/null
done

# 2. Targeted Service Account User binding (scoped directly to Compute Default SA instead of project-wide)
echo "Binding roles/iam.serviceAccountUser specifically on Compute Default SA (${COMPUTE_SA})..."
gcloud iam service-accounts add-iam-policy-binding "${COMPUTE_SA}" \
  --project="${GCP_PROJECT_ID}" \
  --role="roles/iam.serviceAccountUser" \
  --member="serviceAccount:${SA_EMAIL}" >/dev/null

echo "Binding roles/storage.objectViewer to Compute Default SA (${COMPUTE_SA}) for Cloud Build..."
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectViewer" >/dev/null

# 3. Targeted Bucket-level Admin binding for Terraform state bucket (if bucket exists)
STATE_BUCKET="bkt-tf-state-${GCP_PROJECT_ID}-${GITHUB_REPO}"
if gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  echo "Binding roles/storage.admin on Terraform state bucket gs://${STATE_BUCKET}..."
  gcloud storage buckets add-iam-policy-binding "gs://${STATE_BUCKET}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin" >/dev/null 2>&1 || true
fi

echo "IAM bindings successfully applied to GitHub Actions Service Account."
