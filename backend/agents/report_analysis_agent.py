"""
Report Analysis Agent — analyzes uploaded reports and extracts insights.
"""

from __future__ import annotations


class ReportAnalysisAgent:
    """Analyzes uploaded reports and extracts insights."""

    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt

    async def run(self, context: dict) -> dict:
        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        context_str = trim_context_for_llm(context, max_chars, reserved_chars=len(self.prompt) + 200)
        prompt_text = f"{self.prompt}\n\n# REPORT DATA\n\n{context_str}"
        response = await self.llm.generate(prompt_text)
        return {"raw_response": response}
