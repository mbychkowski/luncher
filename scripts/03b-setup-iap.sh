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

echo "Setting up IAP OAuth Brand and Client for project ${GCP_PROJECT_ID}..."

USER_EMAIL="${GCP_USER_EMAIL:-$(gcloud config get-value account 2>/dev/null || echo '')}"

if [ -z "${USER_EMAIL}" ]; then
  echo "Error: Could not determine active gcloud user email. Please ensure you are logged in with 'gcloud auth login'."
  exit 1
fi

# 1. Check if IAP OAuth Brand already exists or create it
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")
BRAND_NAME="projects/${PROJECT_NUMBER}/brands/${PROJECT_NUMBER}"

if gcloud alpha iap oauth-brands describe "${BRAND_NAME}" >/dev/null 2>&1; then
  echo "IAP OAuth Brand already exists: ${BRAND_NAME}"
else
  echo "Creating IAP OAuth Brand for ${GCP_PROJECT_ID} (support email: ${USER_EMAIL})..."
  gcloud alpha iap oauth-brands create \
    --support_email="${USER_EMAIL}" \
    --application_title="Luncher App" \
    --project="${GCP_PROJECT_ID}"
fi

# 2. Check or create IAP OAuth Client
EXISTING_CLIENT=$(gcloud alpha iap oauth-clients list "${BRAND_NAME}" --format="value(name)" 2>/dev/null | head -n 1 || echo "")

if [ -n "${EXISTING_CLIENT}" ]; then
  echo "IAP OAuth Client already exists: ${EXISTING_CLIENT}"
  CLIENT_ID=$(basename "${EXISTING_CLIENT}")
  CLIENT_SECRET=$(gcloud alpha iap oauth-clients describe "${EXISTING_CLIENT}" --format="value(secret)" 2>/dev/null || echo "")
else
  echo "Creating new IAP OAuth Client for Brand ${BRAND_NAME}..."
  CLIENT_OUTPUT=$(gcloud alpha iap oauth-clients create "${BRAND_NAME}" --display_name="luncher-iap-client" --format="yaml")
  CLIENT_ID=$(echo "${CLIENT_OUTPUT}" | grep "name:" | awk '{print $2}' | xargs basename)
  CLIENT_SECRET=$(echo "${CLIENT_OUTPUT}" | grep "secret:" | awk '{print $2}')
fi

echo "IAP OAuth Client ID: ${CLIENT_ID}"

# 3. Sync Client ID and Secret to GitHub Actions if gh CLI is authenticated
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "Syncing IAP OAuth credentials to GitHub Actions repository (${GITHUB_ORG}/${GITHUB_REPO})..."
  gh variable set GCP_IAP_CLIENT_ID --body "${CLIENT_ID}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  if [ -n "${CLIENT_SECRET}" ]; then
    gh secret set GCP_IAP_CLIENT_SECRET --body "${CLIENT_SECRET}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  fi
  echo "Successfully set GCP_IAP_CLIENT_ID and GCP_IAP_CLIENT_SECRET on GitHub!"
else
  echo "gh CLI not available or not logged in. Please manually add these to GitHub Actions:"
  echo "  - Variable 'GCP_IAP_CLIENT_ID': ${CLIENT_ID}"
  echo "  - Secret 'GCP_IAP_CLIENT_SECRET': <CLIENT_SECRET>"
fi
