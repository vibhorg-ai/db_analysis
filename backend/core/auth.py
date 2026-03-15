"""
Authentication and authorization for DB Analyzer AI v5.

Three modes (auto-selected based on config):
1. Keycloak SSO: validates JWT, extracts roles from token claims.
2. API Key: requires X-API-Key header (simple shared secret).
3. Dev mode: no authentication (when neither Keycloak nor API key is configured).

Roles: admin, analyst, viewer. Permissions map per role.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "query_execute", "sandbox_access", "db_manage",
        "optimization_actions", "view_schema", "view_health",
        "view_issues", "chat", "analyze", "report_upload",
    },
    Role.ANALYST: {
        "query_execute", "sandbox_access", "view_schema",
        "view_health", "view_issues", "chat", "analyze",
        "report_upload",
    },
    Role.VIEWER: {
        "view_schema", "view_health", "view_issues", "chat",
    },
}


@dataclass
class UserContext:
    """Represents the authenticated user for a request."""
    username: str = "anonymous"
    roles: list[Role] = field(default_factory=lambda: [Role.ADMIN])
    authenticated: bool = False
    auth_method: str = "none"

    def has_permission(self, permission: str) -> bool:
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False


def _decode_keycloak_token(token: str) -> dict[str, Any]:
    """Decode and validate a Keycloak JWT. Returns claims dict."""
    settings = get_settings()
    try:
        from jose import jwt, JWTError

        jwks_url = (
            f"{settings.keycloak_server_url.rstrip('/')}"
            f"/realms/{settings.keycloak_realm}"
            f"/protocol/openid-connect/certs"
        )

        import httpx
        resp = httpx.get(jwks_url, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()

        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            options={"verify_aud": bool(settings.keycloak_client_id)},
        )
        return claims
    except ImportError:
        logger.warning("python-jose not installed; Keycloak JWT validation unavailable")
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: python-jose required for Keycloak auth",
        )
    except Exception as e:
        logger.debug("Keycloak token validation failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _extract_roles_from_claims(claims: dict[str, Any]) -> list[Role]:
    """Extract roles from Keycloak token claims."""
    settings = get_settings()
    roles: list[Role] = []

    realm_access = claims.get("realm_access", {})
    realm_roles = realm_access.get("roles", [])

    client_id = settings.keycloak_client_id
    resource_access = claims.get("resource_access", {})
    client_roles = resource_access.get(client_id, {}).get("roles", []) if client_id else []

    all_roles = set(realm_roles + client_roles)

    for r in all_roles:
        r_lower = r.lower()
        if r_lower == "admin" or r_lower == "db_admin":
            roles.append(Role.ADMIN)
        elif r_lower == "analyst" or r_lower == "db_analyst":
            roles.append(Role.ANALYST)
        elif r_lower == "viewer" or r_lower == "db_viewer":
            roles.append(Role.VIEWER)

    if not roles:
        roles.append(Role.VIEWER)

    return roles


async def get_user_context(request: Request) -> UserContext:
    """
    Extract user context from request.
    Auto-selects auth mode based on config.
    """
    settings = get_settings()

    if settings.keycloak_server_url:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing Bearer token. Keycloak authentication required.",
            )
        token = auth_header.split(" ", 1)[1].strip()
        claims = _decode_keycloak_token(token)
        roles = _extract_roles_from_claims(claims)
        username = claims.get("preferred_username", claims.get("sub", "unknown"))
        return UserContext(
            username=username,
            roles=roles,
            authenticated=True,
            auth_method="keycloak",
        )

    if settings.api_key:
        key = request.headers.get("X-API-Key", "")
        if not key:
            bearer = request.headers.get("Authorization", "")
            if bearer.startswith("Bearer "):
                key = bearer.split(" ", 1)[1].strip()
        if key == settings.api_key:
            return UserContext(
                username="api_key_user",
                roles=[Role.ADMIN],
                authenticated=True,
                auth_method="api_key",
            )
        raise HTTPException(status_code=401, detail="Invalid API key")

    return UserContext(
        username="dev_user",
        roles=[Role.ADMIN],
        authenticated=False,
        auth_method="none",
    )


def require_permission(permission: str):
    """FastAPI dependency factory that checks the user has a specific permission."""
    async def _check(request: Request) -> UserContext:
        user = await get_user_context(request)
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: '{permission}' required",
            )
        return user
    return _check
