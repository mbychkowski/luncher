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

echo "Enabling Google Cloud APIs for project ${GOOGLE_CLOUD_PROJECT_ID}..."

# Enable APIs needed for Container Building, Artifact Registry, Cloud Run, Gemini Enterprise Agent Platform (GEAP), and BigQuery
for GOOGLE_CLOUD_API in \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  run.googleapis.com \
  servicecontrol.googleapis.com \
  serviceusage.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  apphub.googleapis.com \
    ; do
  echo "Enabling ${GOOGLE_CLOUD_API}..."
  gcloud services enable --project "${GOOGLE_CLOUD_PROJECT_ID}" "${GOOGLE_CLOUD_API}"
done

echo "Google Cloud APIs successfully enabled."

gcloud config set compute/region "${GOOGLE_CLOUD_LOCATION}" >/dev/null 2>&1

echo "Google Cloud default region set to ${GOOGLE_CLOUD_LOCATION}"

# ==============================================================================
# BigQuery Dataset & Menu Data Initialization
# ==============================================================================
BIGQUERY_LOCATION="${BIGQUERY_LOCATION:-US}"
DATASET_ID="catering"
TABLE_ID="menu_items"
MENU_DATA_FILE="data/catering/catering_menu.json"

echo "Initializing BigQuery dataset '${DATASET_ID}' in location '${BIGQUERY_LOCATION}'..."
if bq show --dataset "${GOOGLE_CLOUD_PROJECT_ID}:${DATASET_ID}" >/dev/null 2>&1; then
  echo "Dataset '${GOOGLE_CLOUD_PROJECT_ID}:${DATASET_ID}' already exists."
else
  echo "Creating dataset '${GOOGLE_CLOUD_PROJECT_ID}:${DATASET_ID}'..."
  bq mk --dataset \
    --location="${BIGQUERY_LOCATION}" \
    --description="Catering options and menu items" \
    "${GOOGLE_CLOUD_PROJECT_ID}:${DATASET_ID}"
fi

if [ -f "${MENU_DATA_FILE}" ]; then
  echo "Populating BigQuery table '${DATASET_ID}.${TABLE_ID}' from ${MENU_DATA_FILE}..."
  bq load \
    --replace \
    --source_format=NEWLINE_DELIMITED_JSON \
    --autodetect \
    "${GOOGLE_CLOUD_PROJECT_ID}:${DATASET_ID}.${TABLE_ID}" \
    "${MENU_DATA_FILE}"
  echo "BigQuery table '${DATASET_ID}.${TABLE_ID}' successfully populated."
else
  echo "Warning: Catering menu data file '${MENU_DATA_FILE}' not found. Skipping table population."
fi
# ==============================================================================
# Agent Engine holding the orchestrator's Sessions
# ==============================================================================
# The orchestrator runs on Cloud Run, which injects no engine id, so it needs an
# engine of its own. An engine with no packaged code is a valid target for Sessions.
ENGINE_DISPLAY_NAME="luncher-agent"
ENGINE_API="https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines"
ENGINE_TOKEN=$(gcloud auth print-access-token)

echo "Initializing Agent Engine '${ENGINE_DISPLAY_NAME}' in ${GOOGLE_CLOUD_LOCATION}..."
EXISTING_ENGINE=$(curl -s -H "Authorization: Bearer ${ENGINE_TOKEN}" "${ENGINE_API}" \
  | jq -r --arg n "${ENGINE_DISPLAY_NAME}" \
      '.reasoningEngines[]? | select(.displayName==$n) | .name' | head -1)

if [ -n "${EXISTING_ENGINE}" ]; then
  echo "Agent Engine '${ENGINE_DISPLAY_NAME}' already exists: ${EXISTING_ENGINE##*/}"
else
  ENGINE_ERR=$(curl -s -X POST \
    -H "Authorization: Bearer ${ENGINE_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"displayName\":\"${ENGINE_DISPLAY_NAME}\"}" \
    "${ENGINE_API}" | jq -r '.error.message // empty')
  if [ -n "${ENGINE_ERR}" ]; then
    echo "Error: could not create Agent Engine '${ENGINE_DISPLAY_NAME}': ${ENGINE_ERR}"
    exit 1
  fi
  echo "Agent Engine '${ENGINE_DISPLAY_NAME}' created."
fi
