# Extend Luncher with integration to catering menu service

This is your task, with help from Antigravity. Build an agent that provides lunch menu options for scheduled meetings, pulled from the company's in-house catering service. Menu options are stored in BigQuery and can be accessed via MCP.

## Prerequisites

Ensure that you have the [`agents-cli` skills](https://github.com/google/agents-cli) installed in Antigravity.

* **Antigravity 2.0:** Go to _Settings > Customizations_ and confirm that several `google-agents-cli-*` skills are listed
* **Antigravity CLI:** At the prompt, enter `/skills` and confirm that several `google-agents-cli-*` skills are listed

## Step 1. Create the agent

### 1.1. Agent scaffolding

Initiate a `/grill-me` session, then enter the following prompt and answer any questions:

```
In the `agents` folder, create a new ADK agent named `cater_agent`. Its purpose is to provide catering menu options to serve at a lunch meeting.

Integrate the cater_agent with other agents as follows:
- when the `parallel_info_gatherer` agent invokes `strategy_agent` and `scheduling_agent`, also invoke `cater_agent` in parallel
- then pass the menu suggestions provided by cater_agent to parallel_info_gatherer, to synthesize into a proposal
- when `propose_lunch` is invoked, include a widget to select from the menu suggestions provided by `cater_agent`
- when the user submits their choices, save the catering menu along with the user's other selections

For the initial version, DO NOT implement any actual retrieval of menu items. Instead, always return a the following mock menu suggestions:
`{buffalo chicken wrap, mixed greens salad, chocolate cookie, assorted sodas},
 {veggie tacos, snow pea salad, apple tartlets, tea service},
 {lamb vindaloo, spiced cauliflower, naan, orange-mint spa water}
`
```

### 1.2. Run locally

Enter the following command to start the agents locally:

```
Start all the agents in `/agents/` locally, with hot reloading enabled. If any are already running, stop them and re-start them to reflect the most recent changes.
```

### 1.3. Validate local agent

Visit http://localhost:8080/dev-ui/?app=app and enter a prompt, like `plan a lunch meeting for tuesday`. Verify that the application continues to function, and now includes catering options

## Step 2. First deployment

### 2.1. Deploy

Enter the following prompt to deploy the new agent, and deploy updates to existing agents:
```
Deploy all agents to Agent Platform's Agent Runtime.
```

### 2.2. Validate deployed agent

When all deployments have completed, visit the deployed `luncher_agent` on Agent Runtime and confirm that the catering options are presented.

## Step 3. Access catering data via MCP

### 3.1. Initialize and review BigQuery dataset

Run the BigQuery seed script to create the `catering` dataset and populate the `menu_items` table:

```bash
./scripts/04-cater-agent-bq-seed.sh
```

In Google Cloud console, visit BigQuery and find dataset: `catering`. Within that dataset, find table: `menu_items`. Query it to explore the catering data it contains.

### 3.2. Add MCP connectivity

Initiate a `/grill-me` session, then enter the following prompt and answer any questions:

```
Add a tool to `cater_agent` named `fetch_catering_data`. It should connect to the GCP MCP endpoint for BigQuery, and use that server's `execute_sql` tool to query dataset/table `catering:menu_items` (in the same project that the agent is running in).

fetch_catering_data should return three proposed menus, each of which includes a main dish, a side, dessert, and beverage. Attempt to make each menu thematically consistent.

Update `propose_lunch` and associated methods in other agents to use the dynamically-fetched menu suggestions instead of mock data.
```

### 3.3. Test local agent

When the implementation is complete, visit http://localhost:8080/dev-ui/?app=luncher_agent and enter a prompt, like `plan a lunch meeting for tuesday`. Verify that the application continues to function, and that catering options are now dynamically generated

### 3.4. Redeploy

Run the following to redeploy the modify agents:

```
Redeploy the agents which have changed.
```

### 3.5. Validate local agent

When all deployments have completed, visit the deployed `luncher_agent` on Agent Runtime / Gemini Enterprise and confirm that catering options are now dynamically generated.

## Step 4. Store user preferences as memories

### 4.1. Add memory tools

Initiate a `/grill-me` session, then enter the following prompt and answer any questions:

```
Add a memory feature for dietary preferences. Requirements:
- when luncher_agent receives a prompt that appears to be a dietary preference specification, stop the lunch scheduling process. Instead, focus only on saving the dietary preference.
- cater_agent has a tool for storing user dietary preferences as memories
- when deployed to Agent Runtime, memories are stored using GEAP memory bank
- when running locally, memories are stored in local memory
- before querying for menus, consult the memory service for any stored dietary preferences
- if there are preferences, filter menu suggestions accordingly to present only menus that attendees will enjoy
- when the final response is delivered to the user, append text: "Are there any dietary preferences that I should consider? Specify them and I'll rememember them for the future."
- if the user prompt contains a dietary preference, store it as a memory instead of scheduling a meeting.
```

### 4.2. Validate local agent

When the implementation is complete, visit http://localhost:8080/dev-ui/?app=app and enter a preference prompt, like `my team doesn't like fish`. Verify that the application continues to function, and that catering options filter according to preferences.

> Note: when running locally, memories will be preserved within a session, but not across multiple sessions.

### 4.3. Redeploy

Run the following to redeploy the modify agents:

```
Redeploy the agents which have changed.
```

### 4.4. Validate deployed agent

When all deployments have completed, visit the deployed `luncher_agent` on Agent Runtime / Gemini Enterprise and confirm that memory tools are functional.

## Step 5. Add evaluations

Validate `cater_agent` using the `agents-cli eval` framework to test that it reliably generates themed menus, adheres to dietary constraints, and records memory preferences.

### 5.1. Evaluation scaffolding

Initiate a `/grill-me` session, then enter the following prompt and answer any questions:

```
In `agents/cater_agent/tests/eval`, create an evaluation suite using the `agents-cli eval` framework:

1. Create dataset `tests/eval/datasets/catering-dataset.json` with evaluation cases covering:
   - Basic menu proposal: Requesting catering menu options for a lunch meeting and verifying 3 themed 4-course menus (main, side, dessert, beverage) are returned.
   - Dietary restrictions filtering: Requesting menus with constraints (e.g., vegetarian, gluten-free, no seafood/fish) and ensuring returned items strictly follow the restrictions.
   - Preference memory storage: Storing dietary preferences when prompted (e.g., allergies or restrictions) rather than attempting to schedule a meeting.

2. Create `tests/eval/eval_config.yaml` specifying:
   - `custom_response_quality`: Local LLM-as-judge evaluating accuracy, formatting, and menu completeness on a 1-5 scale.
   - `dietary_filtering`: Custom metric validating that all returned menus strictly adhere to requested dietary and allergen restrictions.
   - `agent_turn_count`: Turn counting metric.

3. Implement custom evaluator functions in `tests/eval/response_quality.py` and `tests/eval/dietary_filtering.py`.
```

### 5.2. Run evaluations locally

Make sure `cater_agent` is running locally (port 8083), then run the evaluation script from the repository root:

```bash
./scripts/06-run-evals.sh cater
```

You can also run evaluation inference and grading directly with `agents-cli`:

```bash
# Generate traces from the local catering agent
uv --directory agents/cater_agent run agents-cli eval generate \
  --dataset tests/eval/datasets/catering-dataset.json \
  --url http://localhost:8083 \
  --app-name cater_agent

# Grade the generated traces against eval_config.yaml
uv --directory agents/cater_agent run agents-cli eval grade \
  --traces agents/cater_agent/artifacts/traces/ \
  --config tests/eval/eval_config.yaml
```

### 5.3. Analyze evaluation results and iterate (Quality Flywheel)

1. **Review Grade Results:**
   Open the generated HTML report in your browser (e.g., `agents/cater_agent/artifacts/grade_results/results_<timestamp>.html`) to inspect scores, judge explanations, and individual case traces.

2. **Diagnose and Fix Failures:**
   - **Low `dietary_filtering` score:** If excluded allergens or non-compliant foods appear in suggestions, adjust the system instructions in `app/agent.py` or enhance SQL query and memory filtering logic in `app/tools.py`.
   - **Low `custom_response_quality` score:** If menus lack 4 courses or miss thematic consistency, clarify the instruction prompt in `app/agent.py`.

3. **Compare Results Across Iterations:**
   After making adjustments to instructions or tool implementations, rerun evaluation and compare the results to ensure scores improved without regressions:

   ```bash
   uv --directory agents/cater_agent run agents-cli eval compare \
     agents/cater_agent/artifacts/grade_results/results_<baseline>.json \
     agents/cater_agent/artifacts/grade_results/results_<new>.json
   ```

## Step 6. (optional). Learn from experience

Run `/learn` and follow the prompts to help Antigravity improve based on learnings from this session

## Step 7. Cleanup


### 7.1. Stop local servers

Enter the following prompt to stop local background processes before deploying:

```
Stop all locally running agents and processes.
```
---

| [⬅️ Previous: 3. Deploying to Cloud & Agent Platform Playground](3_deploy.md) | [📚 Getting Started](../README.md#getting-started) | [Next: 5. Registering to Gemini Enterprise ➡️](5_ge.md) |
| :--- | :---: | ---: |
