# Human message templates (v7)

Use the **Human message** → **Message template** field for each LLM generation step.

---

## v7 vs v4 difference

In **v4**, each of the 16 steps had a unique human message template with `{{flow_context.*}}` variables to receive prior step outputs.

In **v7**, there is only **one template** for both steps: `{{user_input}}`. The Python backend builds the complete prompt (including agent instructions, prior analysis results, and all context) and sends it as `user_input`.

---

## Templates

### chat_response (chat flow)

**Human message template:**
```
{{user_input}}
```

The Python backend sends:
- **`context_data`** (for the **System Prompt** / Message template): schema, health, reports, connection, rules. Add `## Context\n{{context_data}}` in the chat step's System Prompt — see `chat_response_prompt.md`.
- **`user_input`** (for the Human message): conversation only (prior user/assistant turns + current user message).

**Include chat history:** **Unchecked** (v7 manages its own history)

---

### pipeline_agent (db_analysis_amaiz_pipeline flow)

**Message template:**
```
{{user_input}}
```

The Python backend serializes the following into `user_input`:
- The agent's specific prompt (from `prompts/{agent_name}_prompt.md`)
- `# INPUT DATA` section with schema metadata, query, and prior agent outputs
- All relevant context for that specific pipeline stage

**Include chat history:** **Unchecked** (pipeline calls are independent)

---

## Why no `{{flow_context.*}}` in v7?

In v4, AMAIZ orchestrated the pipeline and needed `{{flow_context.*}}` to pass data between steps. In v7:

1. Python runs each agent stage independently.
2. Python accumulates results from prior stages.
3. Before calling the next stage, Python builds a complete prompt that includes all necessary prior results.
4. This complete prompt is sent as `user_input` to the single `pipeline_agent` step.

There is no inter-step data flow within AMAIZ — everything is handled by the Python `AgentOrchestrator`.

---

## Variable reference

| Variable | Available? | Notes |
|----------|-----------|-------|
| `{{user_input}}` | **Yes** | Main input — contains the full prompt from Python |
| `{{flow_context.*}}` | Not used | Only 1 step per flow; no prior steps to reference |
| `{{format_instruction}}` | **Yes** | Use in system prompt if Response JSON schema is set |
| `{{chat_history}}` | Not used | v7 embeds history in `user_input` |
| `{{skill_input}}` | Not used | Not an Agent Builder flow |
| `{{app_config.*}}` | Not used | No app_config in v7 |
