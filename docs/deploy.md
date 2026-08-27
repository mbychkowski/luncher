# Deploying agents to Google Cloud

Once tested locally, deploy your agents to **Gemini Enterprise Agent Platform (GEAP) Agent Runtime** and **Cloud Run** and interact with them in the Cloud Console. All deployment commands below execute directly from the repository root.

### Step 1: Deploying Agents to Google Cloud

In this multi-agent architecture:
- 🎯 **Strategy Agent** (`strat_agent`) and 📅 **Scheduling Agent** (`sched_agent`) deploy to **Gemini Enterprise Agent Platform (GEAP) Agent Runtime**.
- 👑 **Luncher Orchestrator** (`luncher_agent`) deploys as a containerized service on **Cloud Run**.

> **Note — why `sched_agent` is on Agent Runtime.** It stores team bookings in Memory
> Bank, addressed as `reasoningEngines/<ENGINE_ID>`. Agent Runtime injects
> `GOOGLE_CLOUD_AGENT_ENGINE_ID`, so the host *is* the memory host — no separate
> engine to keep alive. Cloud Run injects nothing.

> **Important — the orchestrator must be on Cloud Run, because it renders A2UI.** A2UI is an
> A2A *extension*, negotiated per request: the client sends `X-A2A-Extensions`,
> and the server must echo that header back before the client may interpret the
> surface. Agent Runtime's `/api/` passthrough replaces response headers
> wholesale — nothing the container sets reaches the caller — so the echo never
> arrives and Gemini Enterprise renders a **blank reply, with no error**. Cloud
> Run passes the header through. This is a platform constraint; no code fixes it.

**1. Load the environment.** Every deployed agent gets these.

```bash
source .env
: "${GOOGLE_CLOUD_PROJECT_ID:?not set -- source .env from the repository root}"
: "${GOOGLE_CLOUD_LOCATION:?not set -- source .env from the repository root}"
BASE_ENV="GOOGLE_GENAI_MODEL=${GOOGLE_GENAI_MODEL},GOOGLE_GENAI_LOCATION=${GOOGLE_GENAI_LOCATION},GOOGLE_CLOUD_PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}"
```

**Serve the strategy PDFs from Cloud Storage — optional.** `strat_agent` reads
the PDFs bundled in `agents/strat_agent/data/docs/` unless `STRATEGY_DOCS_BUCKET`
names a bucket. Same image, same code; one variable picks the branch. Skippable.

```bash
export STRATEGY_DOCS_BUCKET="${GOOGLE_CLOUD_PROJECT_ID}-strategy-docs"

gcloud storage buckets create "gs://${STRATEGY_DOCS_BUCKET}" \
  --project "$GOOGLE_CLOUD_PROJECT_ID" --location "$GOOGLE_CLOUD_LOCATION"

gcloud storage cp agents/strat_agent/data/docs/*.pdf "gs://${STRATEGY_DOCS_BUCKET}/"

gcloud storage buckets add-iam-policy-binding "gs://${STRATEGY_DOCS_BUCKET}" \
  --member "serviceAccount:service-$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT_ID" --format='value(projectNumber)')@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role roles/storage.objectViewer

gcloud storage ls "gs://${STRATEGY_DOCS_BUCKET}"
```

The grant goes to the **Agent Runtime service agent** (`gcp-sa-aiplatform-re`),
which `03-setup-iam.sh` provisions — so run this after it. The `ls` should list
eight PDFs. The strategy deploy below picks the variable up on its own.

**2. Deploy the Strategy Agent** to Agent Runtime.

`${VAR:+…}` appends `STRATEGY_DOCS_BUCKET` only when set, so one command covers
both paths. Agent Runtime rejects an env var with an empty value:
`400 INVALID_ARGUMENT … env[4].value; Required field is not set`.

```bash
(cd agents/strat_agent && agents-cli deploy --project "$GOOGLE_CLOUD_PROJECT_ID" --region "$GOOGLE_CLOUD_LOCATION" \
  --update-env-vars "$BASE_ENV${STRATEGY_DOCS_BUCKET:+,STRATEGY_DOCS_BUCKET=$STRATEGY_DOCS_BUCKET}")
```

**3. Deploy the Scheduling Agent** to Agent Runtime — this engine also hosts the
bookings Memory Bank. Takes 5-10 min; add `--no-wait` and poll
`agents-cli deploy --status` if the command may time out.

```bash
(cd agents/sched_agent && agents-cli deploy --project "$GOOGLE_CLOUD_PROJECT_ID" --region "$GOOGLE_CLOUD_LOCATION" \
  --agent-identity \
  --update-env-vars "$BASE_ENV,BIGQUERY_LOCATION=${BIGQUERY_LOCATION}")
```

**4. Resolve the sub-agent card URLs** the orchestrator calls over A2A. The
variable names derive from the sub-agent names in `luncher_agent/app/agent.py` —
a name that does not match is ignored silently and falls back to localhost.

```bash
STRATEGY_AGENT_URL=$(curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines" \
  | jq -r '.reasoningEngines[] | select(.displayName=="strat-agent") | .name' \
  | sed -E "s#projects/(.+)/locations/(.+)/reasoningEngines/(.+)#https://\2-aiplatform.googleapis.com/reasoningEngines/v1/projects/\1/locations/\2/reasoningEngines/\3/api/a2a/app/.well-known/agent-card.json#")

SCHEDULING_AGENT_URL=$(curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines" \
  | jq -r '.reasoningEngines[] | select(.displayName=="sched-agent") | .name' \
  | sed -E "s#projects/(.+)/locations/(.+)/reasoningEngines/(.+)#https://\2-aiplatform.googleapis.com/reasoningEngines/v1/projects/\1/locations/\2/reasoningEngines/\3/api/a2a/app/.well-known/agent-card.json#")

echo "strat: ${STRATEGY_AGENT_URL:-UNRESOLVED}"; echo "sched: ${SCHEDULING_AGENT_URL:-UNRESOLVED}"
```

**5. Resolve the orchestrator's own engine**, created by `02-init-api.sh` to hold
its sessions and Memory Bank. Cloud Run injects nothing, so it is passed
explicitly.

```bash
LUNCHER_ENGINE_ID=$(curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines" \
  | jq -r '.reasoningEngines[] | select(.displayName=="luncher-agent") | .name' \
  | sed -E 's#.*/reasoningEngines/##')

echo "luncher engine: ${LUNCHER_ENGINE_ID:-UNRESOLVED}"
```

**6. Deploy the Luncher Orchestrator** to Cloud Run. `APP_URL` is what the agent
card advertises; without it the card falls back to localhost and no client can
reach the agent.

```bash
LUNCHER_URL="https://luncher-agent-$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT_ID" --format='value(projectNumber)').${GOOGLE_CLOUD_LOCATION}.run.app"
(cd agents/luncher_agent && agents-cli deploy --deployment-target cloud_run \
  --project "$GOOGLE_CLOUD_PROJECT_ID" --region "$GOOGLE_CLOUD_LOCATION" --service-name luncher-agent \
  --update-env-vars "$BASE_ENV,STRATEGY_AGENT_URL=${STRATEGY_AGENT_URL},SCHEDULING_AGENT_URL=${SCHEDULING_AGENT_URL},APP_URL=${LUNCHER_URL},GOOGLE_CLOUD_AGENT_ENGINE_ID=${LUNCHER_ENGINE_ID},GOOGLE_CLOUD_AGENT_ENGINE_LOCATION=${GOOGLE_CLOUD_LOCATION}")
```

> **Important:** give the orchestrator its **own** engine, never `sched_agent`'s — the variable
> selects the session store. Omit it and
> `get_session_service()` silently falls back to `InMemorySessionService`, losing
> session state across restarts.

The orchestrator's own agent card is served at `/a2a/luncher_agent/.well-known/agent-card.json`
(the path carries the ADK `App` name), while both sub-agents serve theirs at `/a2a/app/...`.
