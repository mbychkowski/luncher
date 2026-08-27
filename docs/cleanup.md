## 🗑️ Cleanup

To delete deployed cloud resources and prevent ongoing charges, run the cleanup commands using your environment variables:

```bash
source .env

# 1. Delete Luncher Orchestrator (Cloud Run)
gcloud run services delete luncher-agent --region "$GOOGLE_CLOUD_LOCATION" --project "$GOOGLE_CLOUD_PROJECT_ID" --quiet

# 2. Delete this project's Agent Runtime engines. There is no gcloud surface for
#    these and agents-cli has no delete command, so resolve them over REST.
#    Matching on display name leaves any unrelated engine in the project alone.
#    force=true also drops each engine's sessions and memories -- for sched-agent
#    that is every team booking.
API="https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines"
TOKEN=$(gcloud auth print-access-token)

# luncher-agent's engine survives the move to Cloud Run because it still holds
# that agent's sessions -- drop it from the list to keep them.
for NAME in strat-agent sched-agent luncher-agent; do
  ENGINE=$(curl -s -H "Authorization: Bearer ${TOKEN}" "$API" \
    | jq -r --arg n "$NAME" '.reasoningEngines[]? | select(.displayName==$n) | .name')
  if [ -z "$ENGINE" ]; then echo "skip: no engine named $NAME"; continue; fi
  echo "deleting $NAME ($ENGINE)"
  curl -s -X DELETE -H "Authorization: Bearer ${TOKEN}" \
    "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/${ENGINE}?force=true"
done
```
