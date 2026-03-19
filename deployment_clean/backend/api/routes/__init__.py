"""
API routes package. Exposes a single router (from the monolith module).
Sub-routers (health, etc.) can be split out incrementally.
"""

from __future__ import annotations

from backend.api._routes_monolith import router

__all__ = ["router"]
