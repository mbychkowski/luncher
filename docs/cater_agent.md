# Extend Luncher with integration to catering menu service

This is your task, with help from Antigravity. Build an agent that provides lunch menu options for scheduled meetings, pulled from the company's in-house catering service. Menu options are stored in BigQuery and can be accessed via MCP. 

## Prerequisites
Ensure that you have the [`agents-cli` skills](https://github.com/google/agents-cli) installed in Antigravity.

* **Antigravity 2.0:** Go to _Settings > Customizations_ and confirm that several `google-agents-cli-*` skills are listed
* **Antigravity CLI:** At the prompt, enter `/skills` and confirm that several `google-agents-cli-*` skills are listed

## Step 1. Create the agent

### 1. Agent scaffolding
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

### 2. Run locally

Enter the following command to start the agents locally:

```
Start all the agents in `/agents/` locally. If any are already running, stop them and re-start them to reflect the most recent changes.
```

### 3. Manual test

Visit http://localhost:8080/dev-ui/?app=luncher_agent and enter a prompt, like `plan a lunch meeting for tuesday`. Verify that the application continues to function, and now includes catering options

> Optional: run `/learn` to consolidate insights.

## Step 2. First deployment
[TODO]

## Step 3. Access catering data via MCP
[TODO]

## Step 4. Store user preferences as memories
[TODO]

## Step 5. Add evaluations
[TODO]