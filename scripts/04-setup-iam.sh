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

echo "Adding IAM roles to GitHub Actions Service Account: ${SA_EMAIL}..."

# List of roles required for GitHub Actions to manage and deploy to Cloud Run via Terraform
ROLES=(
    "artifactregistry.admin"
    "cloudbuild.builds.editor"
    "run.admin"
    "iam.serviceAccountUser"
    "iam.serviceAccountTokenCreator"
    "logging.logWriter"
    "storage.admin"
    "resourcemanager.projectIamAdmin"
    "viewer"
)

for role in "${ROLES[@]}"; do
  echo "Binding role roles/${role}..."
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role "roles/$role" \
    --condition=None >/dev/null
done

PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT_ID" --format="value(projectNumber)")
RE_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

echo "Binding role roles/aiplatform.user to Reasoning Engine Service Account: ${RE_SA}..."
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${RE_SA}" \
  --role "roles/aiplatform.user" \
  --condition=None >/dev/null

COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Binding storage.admin & artifactregistry.admin to Compute SA: ${COMPUTE_SA}..."
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role "roles/storage.admin" \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role "roles/artifactregistry.admin" \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role "roles/logging.logWriter" \
  --condition=None >/dev/null

echo "Binding artifactregistry.admin to Cloud Build SA: ${CLOUDBUILD_SA}..."
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role "roles/artifactregistry.admin" \
  --condition=None >/dev/null

echo "IAM bindings successfully applied."
