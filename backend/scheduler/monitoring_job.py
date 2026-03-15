"""Autonomous monitoring: runs monitoring_agent periodically, persists results, broadcasts via WebSocket."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


def _detect_category(alert: Any) -> str:
    """Auto-detect issue category from alert content."""
    text = ""
    if isinstance(alert, dict):
        text = f"{alert.get('title', '')} {alert.get('description', '')} {alert.get('message', '')}".lower()
    else:
        text = str(alert).lower()

    if any(w in text for w in ("lock", "blocking", "deadlock", "waiting")):
        return "locks"
    if any(w in text for w in ("slow", "latency", "cache hit", "seq scan", "buffer", "checkpoint", "replication lag")):
        return "performance"
    if any(w in text for w in ("index", "bloat", "vacuum", "autovacuum", "analyze")):
        return "maintenance"
    if any(w in text for w in ("schema", "column", "table", "constraint", "foreign key")):
        return "schema"
    if any(w in text for w in ("config", "setting", "parameter", "max_connections", "shared_buffers", "work_mem")):
        return "configuration"
    if any(w in text for w in ("permission", "role", "grant", "revoke", "auth", "ssl", "password")):
        return "security"
    return "other"


class MonitoringScheduler:
    """Runs monitoring checks on a configurable interval."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_run: float | None = None

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Monitoring scheduler started (interval: %d min)",
            get_settings().monitoring_interval_minutes,
        )

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Monitoring scheduler stopped")

    async def _run_loop(self) -> None:
        """Main loop: run monitoring, persist results, broadcast."""
        settings = get_settings()
        interval_seconds = settings.monitoring_interval_minutes * 60
        while self._running:
            try:
                await self._run_monitoring_cycle()
            except Exception as e:
                logger.exception("Monitoring cycle failed: %s", e)
            await asyncio.sleep(interval_seconds)

    async def _run_monitoring_cycle(self) -> None:
        """Single monitoring cycle: iterate ALL active connections."""
        start = time.perf_counter()
        logger.info("Monitoring cycle starting")

        from backend.core.health_monitor import HealthMonitor
        monitor = HealthMonitor()
        all_health: dict[str, dict[str, Any]] = {}

        try:
            from backend.api.routes import _active_connections
            for conn_id, info in list(_active_connections.items()):
                connector = info.get("connector")
                engine = info.get("engine")
                if not connector:
                    continue
                try:
                    if engine == "postgres":
                        metrics = await monitor.collect_postgres_metrics(connector)
                    elif engine == "couchbase":
                        metrics = await monitor.collect_couchbase_metrics(connector)
                    else:
                        continue
                    health_data = monitor.compute_health_score(metrics)
                    all_health[conn_id] = health_data
                except Exception as e:
                    logger.debug("Metrics collection failed for %s: %s", conn_id, e)
        except Exception as e:
            logger.debug("Could not collect metrics from active connections: %s", e)

        # Record to time-travel stores for each connection
        for conn_id, health_data in all_health.items():
            try:
                from backend.time_travel import get_performance_history, get_issue_history
                perf = get_performance_history()
                raw_alerts = health_data.get("alerts", [])
                alert_dicts = [{"message": a} if isinstance(a, str) else a for a in raw_alerts]
                perf.record(
                    health_score=int(round(health_data.get("score", 0))),
                    metrics=health_data.get("metrics", {}),
                    alerts=alert_dicts,
                )
                issues = get_issue_history()
                for alert in raw_alerts:
                    cat = _detect_category(alert)
                    if isinstance(alert, dict):
                        issues.record(
                            severity=alert.get("severity", "medium"),
                            title=alert.get("title", "Health alert"),
                            description=alert.get("description", ""),
                            source="monitoring_agent",
                            category=cat,
                            connection_id=conn_id,
                        )
                    else:
                        issues.record(
                            severity="medium",
                            title="Health alert",
                            description=str(alert),
                            source="monitoring_agent",
                            category=cat,
                            connection_id=conn_id,
                        )
            except Exception as e:
                logger.debug("Could not record to time-travel for %s: %s", conn_id, e)

        # Broadcast via WebSocket for each connection
        try:
            from backend.api.websocket import notify_monitoring_complete, notify_health_update
            for conn_id, health_data in all_health.items():
                await notify_health_update({**health_data, "connection_id": conn_id})
            elapsed = time.perf_counter() - start
            await notify_monitoring_complete({"duration_s": round(elapsed, 2), "health": all_health})
        except Exception as e:
            logger.debug("Could not broadcast monitoring results: %s", e)

        self._last_run = time.time()
        logger.info("Monitoring cycle complete (%.2fs)", time.perf_counter() - start)

    @property
    def last_run(self) -> float | None:
        return self._last_run

    @property
    def is_running(self) -> bool:
        return self._running


# Module singleton
_scheduler: MonitoringScheduler | None = None


def get_monitoring_scheduler() -> MonitoringScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = MonitoringScheduler()
    return _scheduler
