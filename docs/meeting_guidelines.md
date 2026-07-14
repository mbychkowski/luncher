# 🏢 Acme Corp: Working Meeting & Catering Guidelines
## 📜 Document Reference: ACME-POL-2026-LUNCH

This document defines the official policies, templates, and budgeting rules for team working sessions and catered lunches at Acme Corp. All coordinating agents must adhere to these policies to ensure fiscal compliance and team safety.

---

## 📅 Section 1: Standard Meeting Templates

For working sessions that include catering, coordinators must follow one of these two approved structures. All times are rigid.

### Template A: Technical Kickoff (90 Minutes)
*   **00:00 - 00:10 (10m)**: Intro & Goal Setting
*   **00:10 - 00:50 (40m)**: Architecture Deep Dive & Engineering Discussion
*   **00:50 - 00:70 (20m)**: Q&A and Action Item Delegation
*   **00:70 - 00:90 (20m)**: Team Lunch & Social Coordination

### Template B: Marketing & Strategy Sync (60 Minutes)
*   **00:00 - 00:15 (15m)**: Monthly Performance Review & Metrics Recap
*   **00:15 - 00:40 (25m)**: Creative Strategy Brainstorming
*   **00:40 - 00:60 (20m)**: Next Steps, Action Items & Catered Lunch

---

## 🍔 Section 2: Catering Budget & Compliance

### 2.1 Fiscal Caps
*   The maximum allowable catering budget is **$20.00 USD per attendee** (excluding sales tax and delivery fees).
*   Any order exceeding this threshold will fail automated expense reconciliation and requires executive VP sign-off.

### 2.2 Vendor Preferences
*   Coordinators must prioritize vendors with a quality rating of **4.5 or higher** in the corporate vendor registry.
*   Approved cuisines include: Healthy (Salads/Bowls), Asian (Noodles/Rice), Mexican, and American (Burgers).

### 2.3 Dietary Inclusion & Safety
*   **Gluten-Free (GF)**: If any attendee indicates a gluten sensitivity or allergy, the catering draft must include at least one certified Gluten-Free entree.
*   **Vegan / Vegetarian (V/VG)**: For teams with vegetarian or vegan members, at least 30% of the total food items ordered must match these dietary designations.

---

## 🤖 Section 3: Agent RAG & Grounding Policies

When building meeting and catering agents on the Agent Platform, developers must enforce the following strict behavior rules in their system instructions:

### 3.1 Grounding Verification Rule (Factuality)
The Agenda Agent **must** only suggest meeting structures that align with the templates defined in Section 1. 
*   If a user requests a custom session length (e.g., "Plan a 3-hour brainstorm"), the agent must politely explain that company policy only permits the 90-minute Technical Kickoff or the 60-minute Marketing Strategy Sync for catered working sessions.
*   The agent must cite the section of this document supporting its structure (e.g., `[ACME-POL-2026-LUNCH §1: Template A]`).

### 3.2 Confidentiality & Budget Compliance
*   Under no circumstance should the agent bypass the $20 per-attendee cap.
*   If a vendor's menu has no options within the budget cap, the agent must notify the user and search for an alternative approved vendor.

### 3.3 State Formatting
All output drafts from the Agenda Agent and Catering Agent must compile their reasoning into a Pydantic-compatible JSON schema, returning clear citations to this document for auditing.
