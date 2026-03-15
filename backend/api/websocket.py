"""WebSocket connection manager for real-time DB Analyzer updates."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Event type constants
WS_HEALTH_UPDATE = "health_update"
WS_HEALTH_ALERT = "health_alert"
WS_ISSUE_NEW = "issue_new"
WS_ISSUE_UPDATE = "issue_update"
WS_SCHEMA_CHANGE = "schema_change"
WS_CONNECTION_CHANGE = "connection_change"
WS_MONITORING_COMPLETE = "monitoring_run_complete"


class ConnectionManager:
    """Manages WebSocket connections for broadcasting events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.debug("WebSocket connected (total: %d)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.debug("WebSocket disconnected (total: %d)", len(self._connections))

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast event to all connected clients."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(message)
        failed: list[WebSocket] = []
        async with self._lock:
            connections = list(self._connections)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.debug("Failed to send to WebSocket: %s", e)
                failed.append(ws)
        if failed:
            async with self._lock:
                for ws in failed:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_personal(self, websocket: WebSocket, event_type: str, data: dict[str, Any]) -> None:
        """Send event to a single client."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await websocket.send_text(json.dumps(message))


# Global singleton
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint handler."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data) if data else {}
                cmd = msg.get("cmd")
                if cmd == "ping":
                    await manager.send_personal(
                        websocket, "pong", {"message": "pong"}
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


# Helper functions for broadcasting specific events


async def notify_health_update(health_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_HEALTH_UPDATE, health_data)


async def notify_health_alert(alert_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_HEALTH_ALERT, alert_data)


async def notify_new_issue(issue_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_ISSUE_NEW, issue_data)


async def notify_schema_change(change_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_SCHEMA_CHANGE, change_data)


async def notify_connection_change(connection_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_CONNECTION_CHANGE, connection_data)


async def notify_monitoring_complete(run_data: dict[str, Any]) -> None:
    await manager.broadcast(WS_MONITORING_COMPLETE, run_data)
