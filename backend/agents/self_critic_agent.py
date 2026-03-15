"""
Self-Critic Agent — reviews all outputs from other agents and removes hallucinations.
"""

from __future__ import annotations


class SelfCriticAgent:
    """Reviews all outputs from other agents and removes hallucinations or weak reasoning."""

    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt

    async def run(self, context: dict) -> dict:
        prior_outputs = {}
        for key, value in context.items():
            if isinstance(value, dict) and "raw_response" in value:
                prior_outputs[key] = value["raw_response"]

        if not prior_outputs:
            return {"raw_response": "No prior agent outputs to review.", "reviewed": False}

        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        review_context = {"agent_outputs": prior_outputs}
        context_str = trim_context_for_llm(review_context, max_chars, reserved_chars=len(self.prompt) + 200)
        prompt_text = f"{self.prompt}\n\n# AGENT OUTPUTS TO REVIEW\n\n{context_str}"
        response = await self.llm.generate(prompt_text)
        return {"raw_response": response, "reviewed": True}
