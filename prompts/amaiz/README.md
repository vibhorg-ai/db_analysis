# AMAIZ prompts — v7 (GenAI app flow)

This folder contains prompts and setup instructions for the **db_analysis** GenAI app in v7.

## Architecture change from v4

In **v4**, the AMAIZ platform orchestrated the entire 16-step pipeline internally. The Python backend called AMAIZ once, and AMAIZ ran all 16 steps sequentially, passing data between steps via `{{flow_context.*}}`.

In **v7**, the Python backend (`AgentOrchestrator`) orchestrates the pipeline. It calls AMAIZ **separately for each agent stage**, sending the full prompt + context each time. AMAIZ now acts as a **single-step LLM endpoint** — it receives a prompt, runs one LLM generation, and returns the response.

### What this means

- The `db_analysis_amaiz_pipeline` flow needs only **1 step** (not 16).
- The `chat` flow stays at **1 step** (same as v4).
- No `{{flow_context.*}}` is needed — the Python code builds the complete prompt with all prior context before each call.
- No `db_connection` step in AMAIZ — connections are managed in the Python backend.
- No `security_agent` step — removed from v7 pipeline.

## Flows


| Flow                         | Steps                | Purpose                                           |
| ---------------------------- | -------------------- | ------------------------------------------------- |
| `chat`                       | 1 (`chat_response`)  | Interactive chat with DB context                  |
| `db_analysis_amaiz_pipeline` | 1 (`pipeline_agent`) | All pipeline agent stages (called once per stage) |


## v7 pipeline stages (orchestrated in Python)

The Python `AgentOrchestrator` runs these stages, calling the `db_analysis_amaiz_pipeline` flow once per stage:


| Batch | Stage                   | Description                                     |
| ----- | ----------------------- | ----------------------------------------------- |
| 1     | `schema_intelligence`   | Schema structure, relationships, index coverage |
| 2     | `workload_intelligence` | Query frequency, hot tables, usage patterns     |
| 3     | `query_analysis`        | Query intent, joins, filters, inefficiencies    |
| 4     | `optimizer`             | Optimized SQL and explanations                  |
| 5     | `index_advisor`         | Index recommendations                           |
| 6     | `blast_radius`          | Change impact and risk assessment               |
| 7     | `self_critic`           | Quality review, contradictions, hallucinations  |
| 8     | `learning_agent`        | Pattern extraction for future runs              |


Additional agents (called on-demand, not in main pipeline): `report_analysis`, `graph_reasoning`, `time_travel`, `monitoring`.

## Files in this folder


| File                                 | Purpose                                    |
| ------------------------------------ | ------------------------------------------ |
| `README.md`                          | This file                                  |
| `SETUP_GUIDE.md`                     | Step-by-step AMAIZ portal configuration    |
| `AGENT_STEP_TYPE_MAPPING.md`         | Step type and behaviour mapping            |
| `HUMAN_MESSAGE_TEMPLATES.md`         | Human message templates for each flow step |
| `INPUT_PARAMS_REFERENCE.md`          | Input params function reference            |
| `pipeline_agent_prompt.md`           | System prompt for the pipeline agent step  |
| `chat_response_prompt.md`            | System prompt for the chat response step   |
| `schemas/pipeline_agent_schema.json` | Response JSON schema for pipeline agent    |
| `schemas/chat_response_schema.json`  | Response JSON schema for chat response     |
| `schemas/README.md`                  | Schema descriptions                        |


