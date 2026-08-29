## 🗑️ Cleanup

To delete deployed cloud resources and prevent ongoing charges, run the cleanup commands using your environment variables:

```bash
source .env

# Delete this project's Agent Runtime engines (luncher-agent, strat-agent, sched-agent, cater-agent).
# There is no gcloud surface for these and agents-cli has no delete command, so resolve them over REST.
# Matching on display name leaves any unrelated engine in the project alone.
# force=true also drops each engine's sessions and memories -- for sched-agent that is every team booking.
API="https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines"
TOKEN=$(gcloud auth print-access-token)

for NAME in luncher-agent strat-agent sched-agent cater-agent; do
  ENGINE=$(curl -s -H "Authorization: Bearer ${TOKEN}" "$API" \
    | jq -r --arg n "$NAME" '.reasoningEngines[]? | select(.displayName==$n) | .name')
  if [ -z "$ENGINE" ]; then echo "skip: no engine named $NAME"; continue; fi
  echo "deleting $NAME ($ENGINE)"
  curl -s -X DELETE -H "Authorization: Bearer ${TOKEN}" \
    "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/${ENGINE}?force=true"
done
```

---

| [⬅️ Previous: 5. Catering Agent](cater_agent.md) | [📚 Getting Started](../README.md#getting-started) | [🏠 Return to README ➡️](../README.md) |
| :--- | :---: | ---: |
