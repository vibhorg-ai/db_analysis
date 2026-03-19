# Input params function reference (v7)

## Do I need an Input params function?

**No.** In v7, Input params functions are **not needed** for either flow step.

---

## Why not?

In v4, Input params functions were used to:
1. Read `flow_context` from prior steps
2. Build a combined human message with all prior outputs
3. Set the human message on `prompt_data`

In v7, the Python backend does all of this before calling AMAIZ:
1. `AgentOrchestrator` accumulates results from prior stages
2. Each agent's `run()` method builds the full prompt (agent instructions + context data)
3. `LLMRouter.generate()` sends this as `user_input`

The `user_input` arrives fully formed. The AMAIZ step just needs to pass `{{user_input}}` to the LLM.

**Chat flow only:** The backend sends two separate inputs for the chat flow:
- **`context_data`** — system context (schema, health, reports, connection, rules). Use in the **Message template (System Prompt)** as `{{context_data}}`.
- **`user_input`** — conversation only (USER:/ASSISTANT: turns). Use in the **Human message** template as `{{user_input}}`.

Every chat invocation uses this split; ensure the chat flow's System Prompt includes `{{context_data}}` and the Human message uses `{{user_input}}`.

---

## If you still want one (optional)

If for any reason you need to preprocess the input in AMAIZ, here's a minimal Input params function:

```python
def prepare_prompt(session_provider, prompt_data=None):
    """
    Minimal input params function for v7.
    Just passes user_input through — no transformation needed.
    """
    user_input = ""
    try:
        if hasattr(session_provider, 'get_user_input'):
            user_input = session_provider.get_user_input() or ""
        elif hasattr(session_provider, 'user_input'):
            user_input = session_provider.user_input or ""
    except Exception:
        user_input = ""

    if prompt_data is not None and hasattr(prompt_data, 'template_variables'):
        tv = prompt_data.template_variables
        tv.update({"user_input": user_input})

    return {"user_input": user_input}
```

Paste this into the **Input params function** field if needed. For most setups, leaving it empty works fine since `{{user_input}}` is a built-in variable.
