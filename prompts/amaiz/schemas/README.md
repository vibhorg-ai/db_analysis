# Response JSON schemas (v7)

These schemas are pasted into each step's **Response JSON schema** field in the AMAIZ UI.

## Schemas

| File | Used by | Description |
|------|---------|-------------|
| `chat_response_schema.json` | `chat` → `chat_response` step | Simple `{message: string}` response for chat |
| `pipeline_agent_schema.json` | `db_analysis_amaiz_pipeline` → `pipeline_agent` step | Simple `{message: string}` response for all pipeline agents |

## v7 vs v4

In v4, each of the 16 pipeline steps had its own detailed response schema (e.g. `query_analysis_schema.json` with fields like `query_intent`, `join_analysis`, `performance_risk`, etc.). The LLM was constrained to return structured JSON matching each schema.

In v7, all agents return **free-form markdown** in a single `message` field. The Python backend receives the raw text and processes it. This simplification was made because:

1. The Python backend handles all orchestration and result aggregation.
2. Free-form markdown gives the LLM more flexibility to provide detailed analysis.
3. The structured parsing (if needed) happens in the Python backend, not in AMAIZ.

## Usage

1. Open the flow step in the AMAIZ UI.
2. Go to the **Prompt** tab.
3. Click the **Response JSON schema** edit button.
4. Paste the entire contents of the matching `.json` file.
5. Click **Done**.

## If you don't need schemas

The Response JSON schema is **optional** in v7. If you encounter issues with the LLM not returning valid JSON matching the schema, you can remove the Response JSON schema entirely. The Python backend does not rely on structured JSON output from AMAIZ — it reads the raw `response.message.message` text.
