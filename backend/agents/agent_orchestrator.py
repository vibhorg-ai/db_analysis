"""
Coordinates which agents run for which request type.

Every agent (parallel or sequential) receives its own LLMRouter and hence
its own AMAIZ session.  This prevents: (a) 409 "session is in use" contention
in parallel batches, (b) AMAIZ conversation-history accumulation across
sequential agents, (c) cancelled sessions from timed-out agents poisoning
the next agent.
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
    ["schema_intelligence", "workload_intelligence", "query_analysis"],
    ["optimizer", "index_advisor", "blast_radius"],
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
        """Run agents according to stages_or_batches.

        Returns updated context with _timing (values in **milliseconds**)
        and _pipeline_run_id.
        """
        context: dict[str, Any] = dict(initial_context)
        timeout = stage_timeout_sec or self._settings.pipeline_stage_timeout
        run_id = str(uuid.uuid4())
        context["_pipeline_run_id"] = run_id

        timing: dict[str, float] = {}
        batches = self._normalize_to_batches(stages_or_batches)

        # Every agent gets its own LLMRouter (and hence its own AMAIZ session).
        # This prevents: (a) 409 contention in parallel batches, (b) conversation
        # history accumulating across sequential agents on a shared session,
        # (c) cancelled-session state from a timed-out agent poisoning the next one.
        for batch in batches:
            if len(batch) == 1:
                stage_name = batch[0]
                start = time.perf_counter()
                try:
                    llm = LLMRouter()
                    agent = self._agent_router.get_agent(stage_name, llm)
                    result = await asyncio.wait_for(agent.run(context), timeout=timeout)
                    context[stage_name] = result
                except asyncio.TimeoutError:
                    logger.warning("Stage %s timed out after %ds", stage_name, timeout)
                    context[stage_name] = {"error": "timeout", "status": "failed"}
                except Exception as e:
                    logger.exception("Stage %s failed: %s", stage_name, e)
                    context[stage_name] = {"error": str(e), "status": "failed"}
                elapsed_ms = (time.perf_counter() - start) * 1000
                timing[stage_name] = elapsed_ms
            else:
                async def run_stage(stage_name: str, llm: LLMRouter) -> tuple[str, dict, float]:
                    t0 = time.perf_counter()
                    try:
                        agent = self._agent_router.get_agent(stage_name, llm)
                        res = await asyncio.wait_for(agent.run(context), timeout=timeout)
                        return (stage_name, res, (time.perf_counter() - t0) * 1000)
                    except asyncio.TimeoutError:
                        logger.warning("Stage %s timed out after %ds", stage_name, timeout)
                        return (stage_name, {"error": "timeout", "status": "failed"}, (time.perf_counter() - t0) * 1000)
                    except Exception as e:
                        logger.exception("Stage %s failed: %s", stage_name, e)
                        return (stage_name, {"error": str(e), "status": "failed"}, (time.perf_counter() - t0) * 1000)

                logger.info("Running parallel batch %s — spawning %d independent LLM sessions",
                            batch, len(batch))
                tasks = [run_stage(name, LLMRouter()) for name in batch]
                batch_results = await asyncio.gather(*tasks)
                for name, result, elapsed_ms in batch_results:
                    context[name] = result
                    timing[name] = elapsed_ms

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
