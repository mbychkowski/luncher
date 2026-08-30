#!/bin/bash

# Copyright 2026 Google LLC
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

set -euo pipefail

# Runs an agent's eval suite against the copy of it running locally: inference
# first, then grading.
#
#   ./scripts/06-run-evals.sh sched
#   ./scripts/06-run-evals.sh luncher tests/eval/datasets/basic-dataset.json
#   ./scripts/06-run-evals.sh luncher --a2a
#
# --a2a drives the A2A endpoint instead of the ADK REST one. They deliver
# different responses to the same prompt: the A2A executor withholds every author
# but the synthesizer, so only that path shows what an A2A client is handed.
#
# The agent must already be serving (see README section 2). Grading reads the
# newest trace file, so a failed inference would otherwise be graded against the
# previous run and report a plausible, unchanged score -- the check below refuses
# a trace older than the agent code that produced it.

AGENT="${1:-}"
case "$AGENT" in
  luncher) DIR="agents/luncher_agent"; PORT=8080; APP="luncher_agent"
           DATASET="tests/eval/datasets/lunch-dataset.json" ;;
  sched)   DIR="agents/sched_agent";   PORT=8082; APP="sched_agent"
           DATASET="tests/eval/datasets/bookings-dataset.json" ;;
  strat)   DIR="agents/strat_agent";   PORT=8081; APP="strat_agent"
           DATASET="tests/eval/datasets/basic-dataset.json" ;;
  cater)   DIR="agents/cater_agent";   PORT=8083; APP="cater_agent"
           DATASET="tests/eval/datasets/catering-dataset.json" ;;
  *) echo "Usage: $0 {luncher|sched|strat|cater} [dataset]"; exit 1 ;;
esac
A2A=false
if [ "${2:-}" = "--a2a" ]; then
  A2A=true
else
  DATASET="${2:-$DATASET}"
fi

if [ ! -f .env ]; then
  echo "Error: .env not found. Run scripts/01-setup-env.sh first."
  exit 1
fi
# shellcheck source=/dev/null
source .env

# Bookings would otherwise be written to the deployed agent's Memory Bank, where
# the cancellation cases delete real records.
unset GOOGLE_CLOUD_AGENT_ENGINE_ID

if ! curl -sf -m 10 "http://localhost:${PORT}/list-apps" >/dev/null; then
  echo "Error: no agent serving on port ${PORT}. Start it with:"
  echo "  uv --directory ${DIR} run main.py"
  exit 1
fi

cd "$DIR"

if [ "$A2A" = true ]; then
  if [ ! -f tests/eval/a2a_generate.py ]; then
    echo "Error: ${AGENT} has no A2A eval harness (tests/eval/a2a_generate.py)."
    exit 1
  fi
  # The card path carries the ADK App name, which is "app" for the sub-agents.
  # Generates and scores in one pass: an A2A artifact is not an ADK trace, and
  # `eval grade` rejects the file rather than reading its parts.
  uv run python tests/eval/a2a_generate.py "$DATASET" "http://localhost:${PORT}" \
    "$(uv run python -c 'from app.agent import app; print(app.name)')"
  exit 0
else
  echo "== inference: ${DATASET} against localhost:${PORT} =="
  # The app name in ADK's REST path is the agent directory, not the ADK App name
  # ("app") that the A2A card path carries; the wrong one 404s every case.
  uv run agents-cli eval generate --dataset "$DATASET" \
    --url "http://localhost:${PORT}" --app-name "$APP"
  TRACE=$(ls -t artifacts/traces/*.json | head -1)
  CONFIG=tests/eval/eval_config.yaml
fi
NEWEST_SOURCE=$(find app -name '*.py' -newer "$TRACE" -print -quit 2>/dev/null || true)
if [ -n "$NEWEST_SOURCE" ]; then
  echo
  echo "Error: ${NEWEST_SOURCE} is newer than ${TRACE}."
  echo "Inference did not run against the current code; grading it would report"
  echo "the previous run's scores. Check the inference output above."
  exit 1
fi

echo
echo "== grading ${TRACE} =="
uv run agents-cli eval grade --traces "$TRACE" --config "$CONFIG"
