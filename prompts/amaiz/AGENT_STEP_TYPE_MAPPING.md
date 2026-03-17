# Agent → Step mapping (v5)

This file maps each flow step to the **step type** you select in the AMAIZ UI when creating a new step.

---

## v5 mapping (2 flows, 2 steps total)

### Flow: `chat`

| Order | Step name | Step type | Behaviour | Purpose |
|-------|-----------|-----------|-----------|---------|
| 1 | `chat_response` | **LLM generation** | **Respond to user** | Interactive chat. v5 sends system prompt + chat history + user message as a single `user_input`. AMAIZ generates and returns the response. |

### Flow: `db_analysis_amaiz_pipeline`

| Order | Step name | Step type | Behaviour | Purpose |
|-------|-----------|-----------|-----------|---------|
| 1 | `pipeline_agent` | **LLM generation** | **Auto continue** | Generic LLM endpoint for all pipeline stages. v5 Python backend calls this flow once per agent stage, sending the full agent prompt + context as `user_input`. |

---

## Comparison with v4

v4 had 16 steps in `db_analysis_amaiz_pipeline`:

| v4 step | v5 equivalent |
|---------|---------------|
| security_agent | **Removed** — not in v5 |
| db_connection | **Removed** — handled in Python backend |
| report_analysis | Handled by `pipeline_agent` (called with report_analysis prompt) |
| schema_intelligence | Handled by `pipeline_agent` (called with schema_intelligence prompt) |
| entity_graph | **Removed** — not in v5 main pipeline |
| workload_intelligence | Handled by `pipeline_agent` (called with workload_intelligence prompt) |
| query_analysis | Handled by `pipeline_agent` (called with query_analysis prompt) |
| query_plan_graph | **Removed** — not in v5 |
| optimizer_reasoning | Merged into `optimizer` in v5 |
| query_rewrite | Merged into `optimizer` in v5 |
| runtime_verification | **Removed** — not in v5 |
| index_advisor | Handled by `pipeline_agent` (called with index_advisor prompt) |
| impact_analysis | **Removed** — not in v5 main pipeline |
| blast_radius | Handled by `pipeline_agent` (called with blast_radius prompt) |
| self_critic | Handled by `pipeline_agent` (called with self_critic prompt) |
| learning_agent | Handled by `pipeline_agent` (called with learning_agent prompt) |

**Key insight:** In v5, all pipeline stages go through the same single `pipeline_agent` AMAIZ step. The differentiation happens in the Python backend, which sends different prompts for each stage.

---

## Behaviour reference

| Behaviour | When to use |
|-----------|-------------|
| **Auto continue** | Continue to next step without messaging user. Used for `pipeline_agent` (pipeline flow). |
| **Respond to user** | Message the user and proceed. Used for `chat_response` (chat flow). |
| **Code** | Not used in v5 AMAIZ setup. |

---

## LLM capabilities

| Step | Required capabilities | Reason |
|------|----------------------|--------|
| `chat_response` | **Contextual QA** | Chat needs to use provided database context |
| `pipeline_agent` | **Contextual QA**, **Planning** | Agents analyze complex multi-part prompts with schema data |

> **Note:** JSON Structured Output is **not required** in v5. Agents return free-form markdown; the Python backend processes raw text responses.

---

## Step type reference

Only **LLM generation** is used in v5. Available step types in the AMAIZ UI for reference:

- **LLM generation** ← Used for both steps
- Search documents (not used)
- LLM citation (not used)
- Single action agent (not used)
- Zero shot agent (not used)
- API invoker (not used — db_connection handled in Python)
- Flow caller (not used)
- Python function (not used — db_connection handled in Python)
- Follow-up suggestions (not used)
