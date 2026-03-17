"""Autonomous Database Advisor scheduler — runs advisory cycles every 15 minutes."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

ADVISOR_INTERVAL_MINUTES = 15


class AdvisorScheduler:
    """Runs the Autonomous Database Advisor on a fixed interval."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_run: float | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Advisor scheduler started (interval: %d min)", ADVISOR_INTERVAL_MINUTES)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Advisor scheduler stopped")

    async def _run_loop(self) -> None:
        interval_seconds = ADVISOR_INTERVAL_MINUTES * 60
        # Initial delay: let the system stabilize before first cycle
        await asyncio.sleep(30)
        while self._running:
            try:
                await self._run_advisory_cycle()
            except Exception as e:
                logger.exception("Advisor cycle failed: %s", e)
            await asyncio.sleep(interval_seconds)

    async def _run_advisory_cycle(self) -> None:
        start = time.perf_counter()
        logger.info("Advisor cycle starting")

        from backend.intelligence.autonomous_advisor import get_advisor_engine
        from backend.core.connection_manager import get_active_connections_snapshot

        engine = get_advisor_engine()
        connections = get_active_connections_snapshot()

        if not connections:
            logger.info("Advisor cycle skipped — no active connections")
            self._last_run = time.time()
            return

        insights = await engine.run_cycle(connections)

        # Broadcast new insights via WebSocket
        if insights:
            try:
                from backend.api.websocket import notify_event
                await notify_event("advisor_insights", {
                    "count": len(insights),
                    "categories": list({i.get("category", "other") for i in insights}),
                })
            except Exception as e:
                logger.debug("Could not broadcast advisor results: %s", e)

        elapsed = time.perf_counter() - start
        self._last_run = time.time()
        logger.info(
            "Advisor cycle complete (%.2fs): %d insights generated",
            elapsed, len(insights),
        )

    @property
    def last_run(self) -> float | None:
        return self._last_run

    @property
    def is_running(self) -> bool:
        return self._running


_scheduler: AdvisorScheduler | None = None


def get_advisor_scheduler() -> AdvisorScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AdvisorScheduler()
    return _scheduler
