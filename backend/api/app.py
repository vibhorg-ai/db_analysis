"""
FastAPI application for DB Analyzer AI v5.
Serves API and WebSocket; Keycloak optional. No code from v3/v4.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.core.config import get_settings
from backend.core.metrics import get_prometheus_text, record_request

from backend.api.routes import router
from backend.api.websocket import websocket_endpoint


# --- Credential Redaction Log Filter ---


class CredentialRedactionFilter(logging.Filter):
    """Redacts password=, api_key=, secret=, token= and postgresql:// credentials in log messages."""

    _REDACT_PATTERNS = [
        (re.compile(r"(?i)password[=:]\s*[^\s&]+", re.IGNORECASE), "password=***REDACTED***"),
        (re.compile(r"(?i)api_key[=:]\s*[^\s&]+", re.IGNORECASE), "api_key=***REDACTED***"),
        (re.compile(r"(?i)secret[=:]\s*[^\s&]+", re.IGNORECASE), "secret=***REDACTED***"),
        (re.compile(r"(?i)token[=:]\s*[^\s&]+", re.IGNORECASE), "token=***REDACTED***"),
        (re.compile(r"postgresql://[^:]+:[^@]+@"), "postgresql://***:***@"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat, replacement in self._REDACT_PATTERNS:
            msg = pat.sub(replacement, msg)
        # LogRecord doesn't allow modifying msg easily; we can't change the output.
        # Use a custom formatter or subclass. For simplicity, we'll modify the record.
        record.msg = msg
        record.args = ()
        return True


# --- Rate Limiter ---


class SlidingWindowRateLimiter:
    """Simple in-memory sliding-window rate limiter. Thread-safe."""

    def __init__(self) -> None:
        self._timestamps: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: float) -> bool:
        with self._lock:
            now = time.monotonic()
            cutoff = now - window_seconds
            timestamps = self._timestamps.get(key, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= max_requests:
                return False
            timestamps.append(now)
            self._timestamps[key] = timestamps
            return True


# --- Middleware ---


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status_code, duration_ms with request_id. Calls record_request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        status_code = response.status_code
        record_request(path, status_code, duration_ms / 1000.0)
        logger = logging.getLogger("backend.api")
        logger.info(
            "method=%s path=%s status_code=%d duration_ms=%.2f request_id=%s",
            request.method,
            path,
            status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Requires X-API-Key or Authorization: Bearer when api_key is set. Skips /health/live."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path == "/health/live":
            return await call_next(request)

        if not self._api_key:
            return await call_next(request)

        key = request.headers.get("X-API-Key") or ""
        if not key and request.headers.get("Authorization", "").startswith("Bearer "):
            key = request.headers.get("Authorization", "").split(" ", 1)[1]

        if key != self._api_key:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


class BodySizeLimitMiddleware:
    """ASGI middleware that rejects requests with Content-Length exceeding the limit."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                size = int(content_length)
                if size > self.max_bytes:
                    response = Response(
                        content='{"detail":"Request entity too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass
        await self.app(scope, receive, send)


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Set HTTPX_REQUEST_TIMEOUT env var from config
    os.environ["HTTPX_REQUEST_TIMEOUT"] = str(settings.HTTPX_REQUEST_TIMEOUT)

    # Configure structured logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    for handler in logging.root.handlers:
        handler.addFilter(CredentialRedactionFilter())

    logger = logging.getLogger("backend.api")
    logger.info(
        "Startup: AMAIZ configured=%s, environment=%s",
        settings.amaiz_configured,
        settings.environment,
    )

    if settings.keycloak_server_url:
        logger.info("Keycloak configured: %s (realm=%s)", settings.keycloak_server_url, settings.keycloak_realm)
    elif settings.api_key:
        logger.info("API key auth active")
    else:
        logger.info("No auth configured; running in dev mode (all endpoints open)")

    # Start monitoring scheduler
    from backend.scheduler.monitoring_job import get_monitoring_scheduler

    scheduler = get_monitoring_scheduler()
    await scheduler.start()

    yield

    await scheduler.stop()
    logger.info("Shutdown")


# --- App Factory ---


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="DB Analyzer AI v5",
        version="5.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware order: last added = first to receive request (inner to outer)
    # Request flow: CORS -> BodySizeLimit -> APIKey -> RequestLogging -> routes
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(APIKeyAuthMiddleware, api_key=settings.api_key)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.body_size_limit_mib * 1024 * 1024,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(
            ["*"]
            if settings.cors_allowed_origins == "*"
            else [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        return {"status": "ok", "version": "5.0.0"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "5.0.0"}

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=get_prometheus_text(), media_type="text/plain; charset=utf-8")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket_endpoint(websocket)

    return app


app = create_app()
