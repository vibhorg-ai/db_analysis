"""
Monitoring agent — detects DB health issues (slow queries, resource pressure, etc.).
"""

from __future__ import annotations


class MonitoringAgent:
    """Detects slow queries, resource pressure, lock contention, replication lag."""

    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt

    async def run(self, context: dict) -> dict:
        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        context_str = trim_context_for_llm(context, max_chars, reserved_chars=len(self.prompt) + 200)
        prompt_text = f"{self.prompt}\n\n# INPUT DATA\n\n{context_str}"
        response = await self.llm.generate(prompt_text)

        result: dict = {"raw_response": response}
        health = context.get("health_metrics") or context.get("health") or context.get("metrics")
        if health is not None:
            result["health_data"] = health
        return result
