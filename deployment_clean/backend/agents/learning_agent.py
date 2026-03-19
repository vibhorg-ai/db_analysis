"""
Learning Agent — stores insights in memory/ and improves future recommendations.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class LearningAgent:
    """Stores insights in memory/ directory. Improves future recommendations."""

    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt
        self._memory_dir = Path(__file__).resolve().parent.parent.parent / "memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    async def run(self, context: dict) -> dict:
        prior_outputs = {}
        for key, value in context.items():
            if isinstance(value, dict) and "raw_response" in value:
                raw = value["raw_response"]
                prior_outputs[key] = str(raw)[:500] if raw else ""

        if not prior_outputs:
            return {"raw_response": "No agent outputs to learn from.", "insights_saved": False}

        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        learn_context = {"agent_outputs": prior_outputs}
        context_str = trim_context_for_llm(learn_context, max_chars, reserved_chars=len(self.prompt) + 200)
        prompt_text = f"{self.prompt}\n\n# OUTPUTS TO LEARN FROM\n\n{context_str}"
        response = await self.llm.generate(prompt_text)

        self._save_insight(response)

        return {"raw_response": response, "insights_saved": True}

    def _save_insight(self, insight: str) -> None:
        """Append insight to memory/insights.json."""
        path = self._memory_dir / "insights.json"
        with self._lock:
            existing: list = []
            if path.exists():
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.append({"timestamp": time.time(), "insight": insight[:2000]})
            if len(existing) > 500:
                existing = existing[-500:]
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def get_insights(self, limit: int = 20) -> list[dict]:
        """Return most recent insights."""
        path = self._memory_dir / "insights.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data[-limit:]
        except Exception:
            return []
