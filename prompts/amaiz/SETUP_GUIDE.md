# db_analysis — AMAIZ Setup Guide (v5)

This guide covers the complete AMAIZ portal configuration for v5. The v5 architecture is fundamentally different from v4: **Python orchestrates the pipeline**, and AMAIZ provides **single-step LLM generation** per call.

**Chat quality:** The backend sends **context** (schema, health, reports, connection) as `context_data` and **conversation** as `user_input`. The chat flow **must** use both in its Message template (e.g. `## Context\n{{context_data}}\n\n## Conversation\n{{user_input}}`). If the template uses only `{{user_input}}`, context was previously bundled inside that string; we now send it in `{{context_data}}` for clearer separation and better model behavior. Ensure your flow template includes `{{context_data}}`.

---

## Overview: What changed from v4


| Aspect                     | v4                                       | v5                                        |
| -------------------------- | ---------------------------------------- | ----------------------------------------- |
| Pipeline orchestration     | AMAIZ (16 sequential steps)              | Python `AgentOrchestrator`                |
| AMAIZ pipeline flow steps  | 16                                       | **1**                                     |
| `{{flow_context.*}}`       | Used extensively                         | **Not used** — Python builds full context |
| `db_connection` step       | In AMAIZ (API invoker / Python function) | **Removed** — handled in Python backend   |
| `security_agent` step      | In AMAIZ                                 | **Removed** — not in v5 pipeline          |
| Per-agent response schemas | 16 different schemas                     | **1 generic schema**                      |


---

## Step 1: Update the `chat` flow

The `chat` flow stays at 1 step. Update the existing `chat_response` step:

### 1.1 Details tab


| Field       | Value                                           |
| ----------- | ----------------------------------------------- |
| Name        | `chat_response`                                 |
| Description | Handles chat interactions with database context |
| Behaviour   | **Respond to user**                             |


### 1.2 LLM tab


| Field                  | Value                                    |
| ---------------------- | ---------------------------------------- |
| Filter by capabilities | **Contextual QA** (recommended)          |
| LLM model              | Pick a model that supports Contextual QA |


### 1.3 Prompt tab


| Field                   | Value        |
| ----------------------- | ------------ |
| Prompt message handling | **Advanced** |


**System instructions → Message template:**

Paste the contents of `chat_response_prompt.md` from this folder:

```
You are DB Analyzer AI, an expert database intelligence assistant. You provide concise, technical, and actionable analysis of databases, schemas, performance metrics, and queries.

Follow these rules:
- Use Markdown in all responses.
- Wrap every SQL/N1QL query in a fenced code block: ```sql ... ```
- Use **bold** for emphasis, `inline code` for column/table names.
- Use numbered lists for sequential steps, bullet lists for non-sequential items.
- Use ## headers to separate major sections.
- Never output raw SQL/N1QL outside of a fenced code block.
- For PostgreSQL: write standard SQL.
- For Couchbase: write N1QL queries with backtick ` for identifiers.
- Never mix query languages.
- Every query MUST use actual table/column names from the provided context.

{{format_instruction}}
```

**Response JSON schema:**  
The chat flow should return an object with a `message` string (see schema below). The v5 backend accepts both a plain string and `{"message": "..."}` from AMAIZ and normalizes to a string for the API response.

Paste the contents of `schemas/chat_response_schema.json`:

```json
{
  "title": "ChatResponse",
  "required": ["message"],
  "type": "object",
  "properties": {
    "message": {
      "type": "string",
      "description": "The assistant response"
    }
  }
}
```

**Human message section:**


| Field                 | Value                                               |
| --------------------- | --------------------------------------------------- |
| Prompt library        | `chat - chat_response - Human prom` (or create new) |
| Message template      | See below ⚠️                                        |
| Input params function | *(leave empty)*                                     |
| Include chat history  | **Unchecked** ⚠️                                    |

**Message template (required for good quality):**  
v5 sends **context** (schema, health, reports, connection, rules) in `{{context_data}}` and **conversation** (user/assistant turns) in `{{user_input}}`. Use **both** so the model sees the database context:

```
Use the following context to answer. Only use table/column names from the context. Do not invent schema.

## Context
{{context_data}}

## Conversation
{{user_input}}
```

If you use only `{{user_input}}`, the model may not receive the full context and answers will be worse (generic or missing schema-aware queries).

> **Important:** v5 manages chat history in the Python backend (`ChatSession`). **Uncheck** "Include chat history" so messages are not duplicated.

### 1.4 Advanced tab

No changes needed. Leave defaults.

---

## Step 2: Update the `db_analysis_amaiz_pipeline` flow

This is the **major change**. Delete all 16 existing steps and create **1 new step**.

### 2.1 Remove existing steps

1. Open **Flows** → **db_analysis_amaiz_pipeline**.
2. Delete all 16 existing steps (security_agent through learning_agent).
3. You should have 0 flow steps.

### 2.2 Create the new step: `pipeline_agent`

Click **+ Create new step** → Select **LLM generation**.

### 2.3 Details tab


| Field       | Value                                                                                                      |
| ----------- | ---------------------------------------------------------------------------------------------------------- |
| Name        | `pipeline_agent`                                                                                           |
| Description | Generic LLM generation step for all pipeline agents. Python backend sends the full prompt per agent stage. |
| Behaviour   | **Respond to user**                                                                                        |

> **WARNING:** Do NOT use "Auto continue" here. In a single-step flow, "Auto continue" causes AMAIZ to wait for a non-existent next step, hanging the request indefinitely. "Respond to user" returns the LLM response immediately.


### 2.4 LLM tab


| Field                  | Value                                              |
| ---------------------- | -------------------------------------------------- |
| Filter by capabilities | **Contextual QA**, **Planning** (recommended)      |
| LLM model              | Pick a model with Contextual QA + Planning support |


> **Note:** JSON Structured Output is no longer required — v5 agents return free-form markdown, not structured JSON. The Python backend parses the raw response.

### 2.5 Prompt tab


| Field                   | Value        |
| ----------------------- | ------------ |
| Prompt message handling | **Advanced** |


**System instructions → Message template:**

Paste the contents of `pipeline_agent_prompt.md` from this folder:

```
You are an expert database analysis AI agent. You will receive specific analysis instructions and database context in the input below.

Follow the instructions precisely:
- Analyze only the data provided in the input.
- Be thorough, specific, and actionable in your analysis.
- Use actual table names, column names, and index names from the provided context.
- Format your response as structured Markdown with clear headings and sections.
- Wrap all SQL queries in ```sql code blocks.
- Do not hallucinate tables, columns, or indexes that are not in the provided context.
- When uncertain, state your confidence level explicitly.

{{format_instruction}}
```

**Response JSON schema:**

Paste the contents of `schemas/pipeline_agent_schema.json`:

```json
{
  "title": "PipelineAgentResponse",
  "required": ["message"],
  "type": "object",
  "properties": {
    "message": {
      "type": "string",
      "description": "The agent analysis response"
    }
  }
}
```

**Human message section:**


| Field                 | Value            |
| --------------------- | ---------------- |
| Message template      | `{{user_input}}` |
| Input params function | *(leave empty)*  |
| Include chat history  | **Unchecked**    |


> The Python backend sends the complete prompt (agent instructions + context data) as `user_input`. No flow context or chat history is needed in AMAIZ — everything is embedded in the single `user_input` string.

### 2.6 Advanced tab

No changes needed. Leave defaults.

---

## Step 3: Routing

1. Go to the **Routing** tab.
2. Set **Type** to **No routing**.
3. If prompted for a **Default flow** or **Fallback flow**, set it to **db_analysis_amaiz_pipeline**.
4. Click **Save**.

---

## Step 4: Other tabs


| Tab                  | Action                                                                                                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prompts**          | You can clean up old v4 prompts that are no longer used. Only `chat - chat_response` and `db_analysis_amaiz_pipeline - pipeline_agent` prompts are needed. |
| **Documents**        | Leave empty (no RAG).                                                                                                                                      |
| **Context entities** | Leave empty.                                                                                                                                               |
| **Configuration**    | No app_config needed for v5.                                                                                                                               |
| **Evaluation**       | Optional.                                                                                                                                                  |
| **Settings**         | Disable input guardrails for testing. Enable streaming if desired.                                                                                         |


---

## Step 5: Deploy and test

1. **Deploy** the updated app.
2. **Simulate** with a simple input:
  - For chat: `"What is a B-tree index?"`
  - For pipeline: The Python backend will send the full prompt automatically when you run an analysis.

---

## Quick checklist


| Where                               | What to do                                                                                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Routing**                         | Type = No routing. Default flow = db_analysis_amaiz_pipeline. Save.                                                                                                                         |
| **chat flow**                       | 1 step: `chat_response`. Prompt = Advanced. System = chat prompt. Human = `{{user_input}}`. Schema = ChatResponse. Chat history = **unchecked**.                                            |
| **db_analysis_amaiz_pipeline flow** | **Delete all 16 steps**. Create 1 step: `pipeline_agent`. Prompt = Advanced. System = pipeline prompt. Human = `{{user_input}}`. Schema = PipelineAgentResponse. Behaviour = **Respond to user**. |
| **Old prompts**                     | Clean up unused v4 prompts in the Prompts tab.                                                                                                                                              |
| **Settings**                        | Disable guardrails for testing.                                                                                                                                                             |


---

## Troubleshooting

### "Genaiapp db_analysis missing configuration for routing"

1. Go to **Routing**.
2. Set **Type** to **No routing**.
3. Set **Default flow** to **db_analysis_amaiz_pipeline**.
4. Click **Save**.
5. Deploy again.

### "Guardrails: Guardrails check [GuardrailPhase.input] on level [ExecutionLevel.app]"

1. Go to **Settings** → **Guardrails**.
2. Turn **off** "Enable toxicity input" and "Enable toxicity output" for testing.
3. Save and retry.

### Chat responses are duplicating history

If chat responses repeat prior messages, verify that **Include chat history** is **unchecked** in the chat_response step's Prompt tab. v5 manages its own chat history and embeds it in `user_input`.

### Pipeline agents all timeout / hang

This is usually caused by the `pipeline_agent` step having **Behaviour = "Auto continue"** instead of **"Respond to user"**. In a single-step flow, "Auto continue" waits for a next step that doesn't exist.

1. Open `db_analysis_amaiz_pipeline` flow → click `pipeline_agent` step → **Details** tab.
2. Change **Behaviour** from "Auto continue" to **"Respond to user"**.
3. Click **Update**, then **redeploy** the app.

The v5 backend also has an automatic fallback: if the pipeline flow fails, it retries with the `chatbot` flow so analysis still works while you fix the pipeline flow.

### Pipeline returns empty or unexpected results

1. Verify the `pipeline_agent` step exists and is the only step in `db_analysis_amaiz_pipeline`.
2. Check that `AMAIZ_FLOW_NAME` in `.env` matches exactly: `db_analysis_amaiz_pipeline`.
3. Check that `AMAIZ_CHAT_FLOW_NAME` in `.env` matches: `chatbot` (or your chat flow name).
4. Check application logs for the actual prompt being sent.

### Response validation error

v5 expects a raw text response from AMAIZ. If the `PipelineAgentResponse` schema causes issues, try removing the Response JSON schema entirely from the `pipeline_agent` step — the Python backend doesn't rely on structured output.

---

## Migration from v4

If you're upgrading from v4:

1. **Keep the app** (`db_analysis`) — no need to recreate it.
2. **Keep the `chat` flow** — just update the step settings (uncheck chat history, update system prompt).
3. **Rebuild `db_analysis_amaiz_pipeline`** — delete all 16 steps, create 1 `pipeline_agent` step.
4. **Clean up** — remove unused prompts from the Prompts tab.
5. **Update `.env`** — flow names remain the same (`chat` and `db_analysis_amaiz_pipeline`), so no .env changes needed.

