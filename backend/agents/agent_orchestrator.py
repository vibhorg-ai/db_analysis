"""
Coordinates which agents run for which request type.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from backend.core.agent_router import AgentRouter
from backend.core.config import get_settings
from backend.core.llm_router import LLMRouter

logger = logging.getLogger(__name__)

FULL_PIPELINE_BATCHES = [
    ["schema_intelligence"],
    ["workload_intelligence"],
    ["query_analysis"],
    ["optimizer"],
    ["index_advisor"],
    ["blast_radius"],
    ["self_critic"],
    ["learning_agent"],
]

QUERY_ONLY_STAGES = ["query_analysis", "optimizer", "self_critic"]

REPORT_ONLY_STAGES = ["report_analysis"]

INDEX_ONLY_STAGES = ["schema_intelligence", "index_advisor"]

MONITORING_STAGES = ["monitoring"]


class AgentOrchestrator:
    """Coordinates agent execution for different pipeline modes."""

    def __init__(
        self,
        agent_router: AgentRouter | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self._agent_router = agent_router or AgentRouter()
        self._llm_router = llm_router or LLMRouter()
        self._settings = get_settings()

    def _normalize_to_batches(self, stages_or_batches: list) -> list[list[str]]:
        """Normalize stages to list of batches. Each item is either str or list of str."""
        batches: list[list[str]] = []
        for item in stages_or_batches:
            if isinstance(item, str):
                batches.append([item])
            else:
                batches.append(list(item))
        return batches

    async def run(
        self,
        initial_context: dict,
        stages_or_batches: list,
        stage_timeout_sec: int | None = None,
    ) -> dict:
        """Run agents according to stages_or_batches. Returns updated context with _timing and _pipeline_run_id."""
        context: dict[str, Any] = dict(initial_context)
        timeout = stage_timeout_sec or self._settings.pipeline_stage_timeout
        run_id = str(uuid.uuid4())
        context["_pipeline_run_id"] = run_id

        timing: dict[str, float] = {}
        batches = self._normalize_to_batches(stages_or_batches)

        for batch in batches:
            if len(batch) == 1:
                stage_name = batch[0]
                start = time.perf_counter()
                try:
                    agent = self._agent_router.get_agent(stage_name, self._llm_router)
                    result = await asyncio.wait_for(agent.run(context), timeout=timeout)
                    context[stage_name] = result
                except asyncio.TimeoutError:
                    logger.warning("Stage %s timed out after %ds", stage_name, timeout)
                    context[stage_name] = {"error": "timeout", "status": "failed"}
                except Exception as e:
                    logger.exception("Stage %s failed: %s", stage_name, e)
                    context[stage_name] = {"error": str(e), "status": "failed"}
                elapsed = time.perf_counter() - start
                timing[stage_name] = elapsed
            else:
                start = time.perf_counter()
                async def run_stage(name: str) -> tuple[str, dict]:
                    try:
                        agent = self._agent_router.get_agent(name, self._llm_router)
                        result = await asyncio.wait_for(agent.run(context), timeout=timeout)
                        return (name, result)
                    except asyncio.TimeoutError:
                        logger.warning("Stage %s timed out after %ds", name, timeout)
                        return (name, {"error": "timeout", "status": "failed"})
                    except Exception as e:
                        logger.exception("Stage %s failed: %s", name, e)
                        return (name, {"error": str(e), "status": "failed"})

                tasks = [run_stage(name) for name in batch]
                results = await asyncio.gather(*tasks)
                for name, result in results:
                    context[name] = result
                elapsed = time.perf_counter() - start
                for name in batch:
                    timing[name] = elapsed / len(batch)  # approximate per-stage share

        context["_timing"] = timing
        return context

    async def run_full(self, context: dict) -> dict:
        """Run FULL_PIPELINE_BATCHES."""
        return await self.run(context, FULL_PIPELINE_BATCHES)

    async def run_query_only(self, context: dict) -> dict:
        """Run QUERY_ONLY_STAGES."""
        return await self.run(context, QUERY_ONLY_STAGES)

    async def run_report_only(self, context: dict) -> dict:
        """Run REPORT_ONLY_STAGES."""
        return await self.run(context, REPORT_ONLY_STAGES)

    async def run_index_only(self, context: dict) -> dict:
        """Run INDEX_ONLY_STAGES."""
        return await self.run(context, INDEX_ONLY_STAGES)

    async def run_monitoring(self, context: dict) -> dict:
        """Run MONITORING_STAGES."""
        return await self.run(context, MONITORING_STAGES)
