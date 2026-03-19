"""Health and AMAIZ health check routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.core.constants import APP_VERSION
from backend.core.instance_id import get_instance_id

router = APIRouter()


@router.get("/health")
async def api_health() -> dict[str, str]:
    """Return status and instance_id so frontend can detect backend restarts."""
    return {"status": "ok", "version": APP_VERSION, "instance_id": get_instance_id()}


@router.get("/health/amaiz")
async def health_amaiz(
    live: bool = Query(False, description="If true, call AMAIZ session_init to verify requests reach AMAIZ"),
) -> dict[str, Any]:
    """
    Health check for AMAIZ integration.
    - Always returns configured and status. With ?live=1: performs real session_init().
    """
    from backend.core.config import get_settings
    from backend.core.amaiz_service import AmaizService

    settings = get_settings()
    configured = settings.amaiz_configured
    result: dict[str, Any] = {
        "configured": configured,
        "status": "ok" if configured else "unconfigured",
        "base_url": (settings.AMAIZ_BASE_URL or "").strip() or None,
    }
    if not configured:
        result["message"] = (
            "AMAIZ not configured. Set AMAIZ_TENANT_ID, AMAIZ_BASE_URL, AMAIZ_API_KEY, "
            "AMAIZ_GENAIAPP_RUNTIME_ID in .env"
        )
        return result

    if live:
        try:
            amaiz = AmaizService()
            session_id = await amaiz.session_init()
            result["live_check"] = {
                "success": True,
                "session_id": f"{session_id[:8]}..." if session_id and len(session_id) > 8 else (session_id or None),
            }
        except Exception as e:
            result["live_check"] = {"success": False, "error": str(e)}
            result["status"] = "degraded"
    return result
