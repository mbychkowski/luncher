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

# Registers a deployed agent with a Gemini Enterprise app over A2A, which is what
# makes its A2UI surfaces render in Gemini Enterprise rather than only in the ADK
# dev UI.
#
#   ./scripts/05-register-gemini-enterprise.sh              # print the payload, POST nothing
#   ./scripts/05-register-gemini-enterprise.sh --apply      # actually register
#   ./scripts/05-register-gemini-enterprise.sh --list       # show what is registered
#   ./scripts/05-register-gemini-enterprise.sh --deregister "NAME" --apply
#
# Requires, beyond .env:
#   GEMINI_ENTERPRISE_APP_ID    the GE app (engine) to register into
#   APP_URL                     base URL of the agent, e.g. the Cloud Run service
#                               root. On Agent Runtime, set AGENT_ENGINE_ID instead
#                               and the /api passthrough URL is built for you.
#   AGENT_APP_NAME              the ADK `App` name, which the card path carries.
#                               Defaults to luncher_agent; sub-agents use "app".
#
# A2UI needs an A2A registration served from Cloud Run: Agent Runtime's /api
# passthrough strips the X-A2A-Extensions echo, so the surface renders as nothing.
#
# Gemini Enterprise calls the agent as an IAM principal, so before the registered
# agent can answer, grant that principal permission to query the deployed agent
# ("Share an agent" in the console, or the binding printed at the end of a dry run).

DRY_RUN=true
ACTION="register"
DEREGISTER_NAME=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) DRY_RUN=false ;;
    --list) ACTION="list" ;;
    --deregister) ACTION="deregister"; DEREGISTER_NAME="${2:-}"; shift ;;
    --deregister=*) ACTION="deregister"; DEREGISTER_NAME="${1#*=}" ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ ! -f .env ]; then
  echo "Error: .env file not found. Please run scripts/01-setup-env.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source .env

GOOGLE_CLOUD_PROJECT_ID="${GOOGLE_CLOUD_PROJECT_ID:-}"
GEMINI_ENTERPRISE_APP_ID="${GEMINI_ENTERPRISE_APP_ID:-}"
# Where the GE app lives. The API host is derived from this: us, eu or global.
GEMINI_ENTERPRISE_LOCATION="${GEMINI_ENTERPRISE_LOCATION:-global}"
AGENT_ENGINE_ID="${AGENT_ENGINE_ID:-}"
AGENT_ENGINE_LOCATION="${GOOGLE_CLOUD_AGENT_ENGINE_LOCATION:-us-central1}"
AGENT_DISPLAY_NAME="${AGENT_DISPLAY_NAME:-Luncher Orchestrator}"
AGENT_DESCRIPTION="${AGENT_DESCRIPTION:-Plans a team lunch aligned to corporate strategy.}"

for required in GOOGLE_CLOUD_PROJECT_ID GEMINI_ENTERPRISE_APP_ID; do
  if [ -z "${!required}" ]; then
    echo "Error: ${required} is not set (.env or environment)."
    exit 1
  fi
done

# Listing and deregistering run before the card fetch: they need only the app,
# which is what makes deregistering an already-dead backend possible.
if [ "$ACTION" = "list" ] || [ "$ACTION" = "deregister" ]; then
  API_HOST="${GEMINI_ENTERPRISE_LOCATION}-discoveryengine.googleapis.com"
  [ "$GEMINI_ENTERPRISE_LOCATION" = "global" ] && API_HOST="discoveryengine.googleapis.com"
  GE_PROJECT="${GEMINI_ENTERPRISE_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT_ID}"
  AGENTS_URL="https://${API_HOST}/v1alpha/projects/${GE_PROJECT}/locations/${GEMINI_ENTERPRISE_LOCATION}"
  AGENTS_URL="${AGENTS_URL}/collections/default_collection/engines/${GEMINI_ENTERPRISE_APP_ID}"
  AGENTS_URL="${AGENTS_URL}/assistants/default_assistant/agents"
  TOKEN=$(gcloud auth print-access-token)
  AGENTS=$(curl -sS -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${GE_PROJECT}" "$AGENTS_URL")

  if [ "$ACTION" = "list" ]; then
    echo "========================================"
    echo "  Registered agents"
    echo "========================================"
    echo "$AGENTS" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if 'error' in d:
    sys.exit('  ' + d['error'].get('message', '')[:300])
for a in d.get('agents', []):
    kind = ('A2A' if 'a2aAgentDefinition' in a
            else 'ADK' if 'adkAgentDefinition' in a else 'other')
    url = ''
    if kind == 'A2A':
        card = a['a2aAgentDefinition'].get('jsonAgentCard') or '{}'
        try: url = json.loads(card).get('url', '')
        except ValueError: url = '<unparseable card>'
    print(f\"  [{kind}] {a.get('displayName')}\")
    print(f\"        id: {a['name'].rsplit('/', 1)[-1]}\")
    if url: print(f'        url: {url}')
"
    exit 0
  fi

  if [ -z "$DEREGISTER_NAME" ]; then
    echo "Error: --deregister needs the agent's display name (see --list)."
    exit 1
  fi
  AGENT_ID=$(echo "$AGENTS" | python3 -c "
import json, sys
want = sys.argv[1]
d = json.load(sys.stdin)
if 'error' in d:
    sys.exit('listing failed: ' + d['error'].get('message', '')[:200])
hits = [a for a in d.get('agents', []) if a.get('displayName') == want]
if not hits:
    sys.exit(f'no agent named {want!r}')
if len(hits) > 1:
    sys.exit(f'{len(hits)} agents named {want!r}; deregister by hand')
print(hits[0]['name'].rsplit('/', 1)[-1])
" "$DEREGISTER_NAME") || exit 1

  echo "  DELETE ${AGENTS_URL}/${AGENT_ID}   (${DEREGISTER_NAME})"
  if [ "$DRY_RUN" = true ]; then
    echo
    echo "Dry run: nothing was deleted. Re-run with --apply."
    exit 0
  fi
  curl -sS -X DELETE "${AGENTS_URL}/${AGENT_ID}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${GE_PROJECT}" \
    | python3 -c "
import json, sys
raw = sys.stdin.read().strip()
d = json.loads(raw) if raw else {}
sys.exit('  failed: ' + json.dumps(d['error'])[:300]) if 'error' in d else print('  deregistered')
"
  exit 0
fi

# The agent serves its own card; registering a copy of what it actually advertises
# beats maintaining a second hand-written one.
if [ -z "${APP_URL:-}" ]; then
  if [ -z "$AGENT_ENGINE_ID" ]; then
    echo "Error: set AGENT_ENGINE_ID (deployed agent) or APP_URL (any A2A endpoint)."
    exit 1
  fi
  APP_URL="https://${AGENT_ENGINE_LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1"
  APP_URL="${APP_URL}/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${AGENT_ENGINE_LOCATION}"
  APP_URL="${APP_URL}/reasoningEngines/${AGENT_ENGINE_ID}/api"
fi

# The card path carries the ADK `App` name, not a literal "app": hardcoding
# /a2a/app/ 404s against an app named otherwise and looks like a broken deploy.
AGENT_APP_NAME="${AGENT_APP_NAME:-luncher_agent}"
CARD_URL="${APP_URL}/a2a/${AGENT_APP_NAME}/.well-known/agent-card.json"
TOKEN=$(gcloud auth print-access-token)

# Cloud Run wants an audience-bound ID token, not the access token Google APIs
# take, so the card fetch mints its own as CARD_FETCH_SERVICE_ACCOUNT. Needs
# serviceAccountOpenIdTokenCreator on that SA, and run.invoker on the service.
CARD_TOKEN="$TOKEN"
case "$APP_URL" in
  *.run.app*)
    AUDIENCE="${APP_URL%%/a2a*}"
    if [ -n "${CARD_FETCH_SERVICE_ACCOUNT:-}" ]; then
      CARD_TOKEN=$(curl -sS -X POST \
        -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
        "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${CARD_FETCH_SERVICE_ACCOUNT}:generateIdToken" \
        -d "{\"audience\":\"${AUDIENCE}\",\"includeEmail\":true}" \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
      if [ -z "$CARD_TOKEN" ]; then
        echo "Error: could not mint an ID token as ${CARD_FETCH_SERVICE_ACCOUNT}."
        exit 1
      fi
    else
      CARD_TOKEN=$(gcloud auth print-identity-token 2>/dev/null || true)
    fi
    ;;
esac

echo "========================================"
echo "  Fetching agent card"
echo "========================================"
echo "  ${CARD_URL}"

CARD=$(curl -sS -f -H "Authorization: Bearer ${CARD_TOKEN}" "$CARD_URL") || {
  echo "Error: could not fetch the agent card. Is the agent deployed and reachable?" >&2
  exit 1
}

# Validate basic card structure
python3 - "$CARD" <<'PY'
import json, sys

card = json.loads(sys.argv[1])
missing = [
    field
    for field in ("protocolVersion", "name", "url", "version", "capabilities", "skills")
    if not card.get(field)
]
if missing:
    sys.exit(f"Error: agent card is missing required fields: {', '.join(missing)}")

extensions = (card.get("capabilities") or {}).get("extensions") or []
print(f"  ok: {card['name']} v{card['version']}, protocol {card['protocolVersion']}")
print(f"  url: {card['url']}")
for ext in extensions:
    print(f"  extension: {ext.get('uri')}")
PY

API_HOST="${GEMINI_ENTERPRISE_LOCATION}-discoveryengine.googleapis.com"
[ "$GEMINI_ENTERPRISE_LOCATION" = "global" ] && API_HOST="discoveryengine.googleapis.com"

# The GE app need not live in the project the agents run in.
GE_PROJECT="${GEMINI_ENTERPRISE_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT_ID}"
REGISTER_URL="https://${API_HOST}/v1alpha/projects/${GE_PROJECT}"
REGISTER_URL="${REGISTER_URL}/locations/${GEMINI_ENTERPRISE_LOCATION}/collections/default_collection"
REGISTER_URL="${REGISTER_URL}/engines/${GEMINI_ENTERPRISE_APP_ID}/assistants/default_assistant/agents"

# jsonAgentCard is a *string* holding the card, not a nested object.
PAYLOAD=$(python3 - "$CARD" "$AGENT_DISPLAY_NAME" "$AGENT_DESCRIPTION" <<'PY'
import json, sys

card, display_name, description = sys.argv[1], sys.argv[2], sys.argv[3]
# Re-serialised compactly so the embedded string does not carry the formatting
# whitespace of whatever served the card.
compact = json.dumps(json.loads(card), separators=(",", ":"))
print(json.dumps({
    "displayName": display_name,
    "description": description,
    "a2aAgentDefinition": {"jsonAgentCard": compact},
}))
PY
)

echo
echo "========================================"
echo "  Registration request"
echo "========================================"
echo "  POST ${REGISTER_URL}"

if [ "$DRY_RUN" = true ]; then
  echo
  echo "$PAYLOAD" | python3 -m json.tool
  echo
  echo "Dry run: nothing was sent. Re-run with --apply to register."
  echo
  echo "Gemini Enterprise calls the agent as its own principal, so it also needs"
  echo "permission to query the deployed agent. In the console this is Share on the"
  echo "agent; the principal takes the form:"
  echo
  echo "  principal://agents.global.org-ORG_ID.system.id.goog/resources/discoveryengine"
  echo "    /projects/PROJECT_NUMBER/locations/${GEMINI_ENTERPRISE_LOCATION}"
  echo "    /collections/default_collection/engines/${GEMINI_ENTERPRISE_APP_ID}"
  echo
  echo "granted aiplatform.reasoningEngines.query on the deployed agent."
  exit 0
fi

# Registering is a plain POST and the API mints an id per call, so anything
# already under this display name is removed first. Re-registering after a
# redeploy then refreshes the stored card instead of adding a second entry --
# and two entries of one name are what --deregister refuses to resolve.
EXISTING_IDS=$(curl -sS -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Goog-User-Project: ${GE_PROJECT}" "$REGISTER_URL" | python3 -c "
import json, sys
want = sys.argv[1]
d = json.load(sys.stdin)
if 'error' in d:
    sys.exit('listing failed: ' + d['error'].get('message', '')[:200])
for a in d.get('agents', []):
    if a.get('displayName') == want:
        print(a['name'].rsplit('/', 1)[-1])
" "$AGENT_DISPLAY_NAME") || exit 1

for existing_id in $EXISTING_IDS; do
  echo "  replacing registration ${existing_id}"
  curl -sS -X DELETE "${REGISTER_URL}/${existing_id}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${GE_PROJECT}" >/dev/null
done

RESPONSE=$(curl -sS -X POST "$REGISTER_URL" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GE_PROJECT}" \
  -d "$PAYLOAD")

echo "$RESPONSE" | python3 -m json.tool

# A rejected POST still returns a JSON body, so the exit status alone says nothing.
echo "$RESPONSE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if 'error' in d:
    sys.exit('Registration failed: ' + d['error'].get('message', '')[:300]
             + '\n  Check GEMINI_ENTERPRISE_APP_ID and GEMINI_ENTERPRISE_PROJECT_ID'
             + ' against the console; the app id is not the project id.')
" || exit 1

# An A2A registration makes GE fetch the card's url itself, as the GE project's
# Discovery Engine service agent. On Cloud Run that needs run.invoker, and the
# 401 it fails with otherwise says the credential is *missing*, so no grant on
# the agent's own identity substitutes for it.
case "$APP_URL" in
  *.run.app*)
    GE_PROJECT_NUMBER=$(gcloud projects describe "$GE_PROJECT" --format="value(projectNumber)")
    DE_SA="service-${GE_PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
    RUN_SERVICE="${CLOUD_RUN_SERVICE:-luncher-agent}"
    RUN_REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
    echo
    echo "Granting run.invoker on ${RUN_SERVICE} to ${DE_SA}..."
    if gcloud run services add-iam-policy-binding "$RUN_SERVICE" \
         --region "$RUN_REGION" --project "$GOOGLE_CLOUD_PROJECT_ID" \
         --member "serviceAccount:${DE_SA}" \
         --role "roles/run.invoker" >/dev/null 2>&1; then
      echo "  ok"
    else
      echo "  FAILED. Without it every turn returns 401 CREDENTIALS_MISSING. Run:"
      echo "    gcloud run services add-iam-policy-binding ${RUN_SERVICE} \\"
      echo "      --region ${RUN_REGION} --project ${GOOGLE_CLOUD_PROJECT_ID} \\"
      echo "      --member serviceAccount:${DE_SA} --role roles/run.invoker"
    fi
    ;;
esac

echo
echo "Registered. If the agent answers in Gemini Enterprise but renders no surface,"
echo "check that the Gemini Enterprise principal can query the deployed agent."
