# Registering to Gemini Enterprise

### Find your Gemini Enterprise app ID

Open the [Gemini Enterprise apps console](https://console.cloud.google.com/gemini-enterprise/apps),
select the project holding the app, and copy the value in the **ID** column:

<img src="docs/images/gemini-enterprise-app-id.png" alt="Gemini Enterprise app ID column" width="273">

Take the **ID**, not the app's **Name** beside it — the two differ only by a
middle segment (`gemini-enterprise-17811218_1781121851843` against
`gemini-enterprise-1781121851843`), and the name fails as
`404 Engine "..." does not exist`. It goes in `GEMINI_ENTERPRISE_APP_ID`.

If the app lives in a different project from the agents, note that project too
and pass it as `GEMINI_ENTERPRISE_PROJECT_ID`; unset, the script uses
`GOOGLE_CLOUD_PROJECT_ID`.

---

### Registering with Gemini Enterprise (`04-register-gemini-enterprise.sh`)

Register the orchestrator as an **A2A** agent. This is not a preference: Gemini
Enterprise learns that an agent can render A2UI from its **agent card**, and only an
A2A registration has one. An ADK registration authenticates fine but renders every
surface as raw JSON.

**1. Resolve the orchestrator's service root.** Already set as `$LUNCHER_URL` if
you are in the shell that deployed it; this reads it back in a new one.

```bash
LUNCHER_URL=$(gcloud run services describe luncher-agent \
  --region "$GOOGLE_CLOUD_LOCATION" --project "$GOOGLE_CLOUD_PROJECT_ID" \
  --format='value(status.url)')

echo "luncher: ${LUNCHER_URL:-UNRESOLVED}"
```

**2. Register.** Both IDs come from Step 2. Drop `--apply` to print the payload
without sending it.

```bash
GEMINI_ENTERPRISE_APP_ID="gemini-enterprise-..." \
GEMINI_ENTERPRISE_PROJECT_ID="project-holding-the-ge-app" \
APP_URL="$LUNCHER_URL" \
  ./scripts/04-register-gemini-enterprise.sh --apply
```

> **Important:** an A2A registration makes GE call the agent card's `url`
> **directly**, so the Discovery Engine service agent of the GE app's project —
> `service-<GE_PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com` —
> needs `roles/run.invoker` on the orchestrator's Cloud Run service. The script
> grants it after registering and prints the command if that fails.
>
> Without it every turn fails `401 UNAUTHENTICATED / CREDENTIALS_MISSING` —
> *"Request is missing required authentication credential."* The body says
> **missing**, not invalid: GE has no credential to send, so nothing is rejected
> and **no grant on the agent's own identity can fix it**.

---

### Step 4: Grant yourself access to the registered agent

Registering publishes the agent; it does not entitle anyone to use it. Until you
are granted a role on it, it will not answer for you in the Gemini Enterprise app.

**Apps > your app > Agents > Luncher Orchestrator > User permissions > Add user**,
then your own address with the **Agent User** role:

<img src="docs/images/gemini-enterprise-agent-user.png" alt="Add user permissions to the agent" width="497">

The **All users** member type covers everyone in the organization, which is the
option to use when running this as a workshop for a room.

> **Note:** the tab shows *"This agent is not integrated with Agent Registry and
> Gateway policies will not be applied."* That is expected for an A2A
> registration and is not an error.

---

### Troubleshooting registration

Not part of the happy path. Both commands read the **app**, not the agent, so
they need the same two IDs — exported here, since the register command above set
them for one invocation only.

```bash
export GEMINI_ENTERPRISE_APP_ID="gemini-enterprise-..."
export GEMINI_ENTERPRISE_PROJECT_ID="project-holding-the-ge-app"
```

See what is currently registered, and whether it registered as A2A or ADK:

```bash
./scripts/04-register-gemini-enterprise.sh --list
```

Remove a stale entry — a registration pointing at a deleted backend, or an ADK
one that renders surfaces as raw JSON. The display name comes from `--list`:

```bash
./scripts/04-register-gemini-enterprise.sh \
  --deregister "Luncher Agent (A2A)" --apply
```

---

### Step 5: Test in Gemini Enterprise

This is the surface the whole deployment is aimed at: the only one that renders
the orchestrator's A2UI.

**1. Open the webapp.** **Gemini Enterprise > your app > Overview** carries the
URL under *"Your Gemini Enterprise webapp is ready"*:

```
https://vertexaisearch.cloud.google.com/home/cid/<YOUR_APP_CID>
```

**2. Pick the agent.** In the left rail choose **Agents**. The orchestrator is
under **From your organization** as *Luncher Orchestrator* — the display name it
was registered with. If it is missing, nobody has been granted a role on it
(Step 4).

**3. Send a message**, for example:

```
Plan a team lunch meeting for next week that aligns with our corporate strategy.
```

The reply is the same A2UI proposal card the dev UI renders, and here the
**Book this lunch** button works: Gemini Enterprise dispatches the action back to
the agent, which delegates to `sched_agent` to write the booking.

---

### Also worth opening

- **Sub-agents:** **Console > Agent Platform > Agents > Deployments**, then
  `strat-agent` or `sched-agent`. The **Playground** tab prompts one directly,
  which is the quickest way to isolate a failure to a single agent. Traces,
  Sessions, Identity and Logs cover the same deployment.
  - `luncher-agent` appears in that list but is **not** a deployment: it is the
    engine `02-init-api.sh` created to hold the orchestrator's sessions.
    It has no code and nothing to invoke.
  - The **Dashboard** tab needs `apphub.googleapis.com`, enabled by
    `02-init-api.sh`. On a project set up before that, it reports `API is not
    enabled`, and only that tab is affected.
- **The orchestrator's own dev UI**, served from its Cloud Run service. The
  service is not public, so proxy it rather than opening the URL directly:

  ```bash
  gcloud run services proxy luncher-agent \
    --region "$GOOGLE_CLOUD_LOCATION" --project "$GOOGLE_CLOUD_PROJECT_ID" --port 8080
  ```

  then `http://localhost:8080`.
- **Across the project:** **Console > Logging > Log Explorer** and **Cloud
  Trace** for execution logs and span attributes from every agent turn.

---

| [⬅️ Previous: 3. Deploying to Cloud](deploy.md) | [📚 Getting Started](../README.md#getting-started) | [Next: 5. Catering Agent ➡️](cater_agent.md) |
| :--- | :---: | ---: |