"""
Couchbase connector for DB Analyzer AI v7.
Uses acouchbase AsyncCluster for async Couchbase access.
"""

from __future__ import annotations

import asyncio
import logging
import re
import selectors
from datetime import timedelta
from typing import Any

from backend.core.config import get_settings

from .base import ConnectionResult, is_dangerous_query

logger = logging.getLogger(__name__)

# Default timeouts (seconds)
DEFAULT_WAIT_UNTIL_READY_TIMEOUT = 10
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_QUERY_TIMEOUT = 30
DEFAULT_MANAGEMENT_TIMEOUT = 30

_loop_patched = False


def _patch_acouchbase_event_loop() -> None:
    """Patch acouchbase LoopValidator so it never closes a running event loop.

    On Windows, uvicorn uses ProactorEventLoop which lacks add_reader/remove_reader.
    The SDK's LoopValidator tries to close it and create a SelectorEventLoop,
    but closing a running loop raises RuntimeError. We override _get_working_loop
    to create a new SelectorEventLoop without closing the running one.
    """
    global _loop_patched
    if _loop_patched:
        return
    try:
        from acouchbase import LoopValidator

        original = LoopValidator._get_working_loop

        @staticmethod  # type: ignore[misc]
        def _safe_get_working_loop():
            try:
                evloop = asyncio.get_running_loop()
            except RuntimeError:
                evloop = None

            if evloop and LoopValidator._is_valid_loop(evloop):
                return evloop

            selector = selectors.SelectSelector()
            new_loop = asyncio.SelectorEventLoop(selector)
            return new_loop

        LoopValidator._get_working_loop = _safe_get_working_loop
        _loop_patched = True
        logger.debug("Patched acouchbase LoopValidator for running event loop compatibility")
    except (ImportError, AttributeError):
        pass


def _normalize_conn_string(raw: str) -> str:
    """Ensure connection string has couchbase:// scheme and strip SDK-managed ports."""
    raw = raw.strip()
    if not raw:
        return raw
    if not raw.startswith(("couchbase://", "couchbases://")):
        if re.match(r"^[\d.]+:\d+$", raw) or re.match(r"^[^/:]+:\d+$", raw):
            raw = raw.rsplit(":", 1)[0]
        raw = f"couchbase://{raw}"
    return raw


def _normalize_error(exc: BaseException, conn_str: str, bucket_name: str) -> str:
    """Map common Couchbase/network errors to user-friendly messages."""
    if isinstance(exc, ImportError):
        return "Couchbase SDK not installed. Run: pip install couchbase"

    msg = str(exc).lower()
    if any(
        x in msg
        for x in (
            "could not resolve host",
            "getaddrinfo failed",
            "nodename nor servname provided",
            "connection refused",
            "connection reset",
            "no route to host",
            "timed out",
            "timeout",
            "unambiguous_timeout",
        )
    ):
        return f"Cannot reach Couchbase server at {conn_str}. Check the connection string and that the host is reachable."

    if any(
        x in msg
        for x in (
            "authentication failed",
            "invalid credentials",
            "authentication exception",
        )
    ):
        return "Invalid username or password for Couchbase."

    if (
        "bucket not found" in msg
        or "bucket does not exist" in msg
        or ("bucket '" in msg and "does not exist" in msg)
    ):
        return f"Bucket '{bucket_name}' does not exist on the cluster."

    return str(exc)


class CouchbaseConnector:
    """Async Couchbase connector implementing ConnectorProtocol."""

    def __init__(
        self,
        connection_string: str | None = None,
        bucket: str | None = None,
        username: str | None = None,
        password: str | None = None,
        *,
        wait_until_ready_timeout: float = DEFAULT_WAIT_UNTIL_READY_TIMEOUT,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        query_timeout: float = DEFAULT_QUERY_TIMEOUT,
        management_timeout: float = DEFAULT_MANAGEMENT_TIMEOUT,
    ) -> None:
        self._connection_string = connection_string
        self._bucket_name = bucket
        self._username = username
        self._password = password
        self._wait_until_ready_timeout = wait_until_ready_timeout
        self._connect_timeout = connect_timeout
        self._query_timeout = query_timeout
        self._management_timeout = management_timeout
        self._cluster: Any = None
        self._bucket: Any = None
        self._resolved_bucket_name: str | None = None

    def _resolve_params(self) -> tuple[str, str, str, str]:
        """Resolve connection params from constructor or config."""
        s = get_settings()
        conn = self._connection_string or s.couchbase_connection_string
        bucket = self._bucket_name or s.couchbase_bucket
        user = self._username or s.couchbase_username
        pwd = self._password or s.couchbase_password
        conn = _normalize_conn_string(conn or "") or "couchbase://localhost"
        return (conn, bucket or "", user or "", pwd or "")

    async def connect(self) -> ConnectionResult:
        conn_str, bucket_name, username, password = self._resolve_params()
        if not bucket_name:
            return ConnectionResult(
                success=False,
                message="Couchbase bucket name not set",
                details={},
            )

        try:
            _patch_acouchbase_event_loop()

            from acouchbase.cluster import AsyncCluster
            from couchbase.auth import PasswordAuthenticator
            from couchbase.options import ClusterOptions, ClusterTimeoutOptions

            auth = PasswordAuthenticator(username, password)
            timeout_opts = ClusterTimeoutOptions(
                connect_timeout=timedelta(seconds=self._connect_timeout),
                query_timeout=timedelta(seconds=self._query_timeout),
                management_timeout=timedelta(seconds=self._management_timeout),
            )
            opts = ClusterOptions(auth, timeout_options=timeout_opts)

            loop = asyncio.get_running_loop()
            self._cluster = await AsyncCluster.connect(conn_str, opts, loop=loop)

            await self._cluster.wait_until_ready(
                timedelta(seconds=self._wait_until_ready_timeout)
            )

            self._bucket = self._cluster.bucket(bucket_name)
            await self._bucket.on_connect()
            self._resolved_bucket_name = bucket_name

            result = self._cluster.query("SELECT 1 AS ping")
            rows: list[dict[str, Any]] = []
            async for row in result.rows():
                if hasattr(row, "keys"):
                    rows.append(dict(row))
                elif isinstance(row, dict):
                    rows.append(row)
                else:
                    rows.append({"value": row})

            return ConnectionResult(
                success=True,
                message="Connected",
                details={"bucket": bucket_name},
            )

        except ImportError as e:
            msg = _normalize_error(e, conn_str, bucket_name)
            logger.exception("Couchbase connection failed: %s", msg)
            return ConnectionResult(success=False, message=msg, details={})
        except Exception as e:
            try:
                from couchbase.exceptions import (
                    AuthenticationException,
                    BucketDoesNotExistException,
                    BucketNotFoundException,
                    UnAmbiguousTimeoutException,
                )

                if isinstance(e, UnAmbiguousTimeoutException):
                    msg = f"Cannot reach Couchbase server at {conn_str}. Check the connection string and that the host is reachable."
                elif isinstance(e, AuthenticationException):
                    msg = "Invalid username or password for Couchbase."
                elif isinstance(e, (BucketNotFoundException, BucketDoesNotExistException)):
                    msg = f"Bucket '{bucket_name}' does not exist on the cluster."
                else:
                    msg = _normalize_error(e, conn_str, bucket_name)
            except ImportError:
                msg = _normalize_error(e, conn_str, bucket_name)

            logger.exception("Couchbase connection failed: %s", msg)
            return ConnectionResult(success=False, message=msg, details={})

    async def disconnect(self) -> None:
        if self._cluster:
            try:
                await self._cluster.close()
            except RuntimeError as e:
                if "event loop" in str(e).lower():
                    logger.debug("Ignoring event loop error during Couchbase disconnect: %s", e)
                else:
                    logger.warning("Error closing Couchbase cluster: %s", e)
            except Exception as e:
                logger.warning("Error closing Couchbase cluster: %s", e)
            finally:
                self._cluster = None
                self._bucket = None
                self._resolved_bucket_name = None

    async def health_check(self) -> dict[str, Any]:
        if not self._cluster:
            return {"connected": False, "accessible": False, "error": "Not connected"}

        try:
            ping_result = await self._cluster.ping()
            has_endpoints = bool(ping_result and getattr(ping_result, "endpoints", None))
            bucket_name = (
                getattr(self._bucket, "name", None) if self._bucket else None
            ) or self._resolved_bucket_name

            return {
                "connected": True,
                "accessible": has_endpoints,
                "bucket": bucket_name,
                "ping": "ok" if has_endpoints else "no_response",
            }
        except Exception as e:
            logger.warning("Couchbase health check failed: %s", e)
            return {"connected": False, "accessible": False, "error": str(e)}

    async def fetch_bucket_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"bucket_name": None, "item_count": None}
        if not self._cluster or not self._bucket:
            return info

        bucket_name = getattr(self._bucket, "name", None) or self._resolved_bucket_name
        info["bucket_name"] = bucket_name

        if bucket_name:
            try:
                from couchbase.options import QueryOptions

                q = f"SELECT COUNT(*) AS n FROM `{bucket_name}`"
                result = self._cluster.query(
                    q, QueryOptions(timeout=timedelta(seconds=5))
                )
                async for row in result.rows():
                    if isinstance(row, dict) and "n" in row:
                        info["item_count"] = row["n"]
                    elif hasattr(row, "get"):
                        info["item_count"] = row.get("n")
                    break
            except Exception as e:
                logger.debug("Could not fetch bucket item count: %s", e)
        return info

    async def execute_read_only(
        self, query: str, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]]:
        if is_dangerous_query(query):
            raise ValueError(
                "Destructive or write operations are not allowed without authorization"
            )
        if not self._cluster:
            raise RuntimeError("Not connected; call connect() first")

        from couchbase.options import QueryOptions

        opts = QueryOptions(timeout=timedelta(seconds=self._query_timeout))
        result = self._cluster.query(query, opts, *args, **kwargs)

        max_rows = 50_000
        rows: list[dict[str, Any]] = []
        async for row in result.rows():
            if len(rows) >= max_rows:
                logger.warning("Couchbase execute_read_only capped at %d rows", max_rows)
                break
            if hasattr(row, "keys"):
                rows.append(dict(row))
            elif isinstance(row, dict):
                rows.append(row)
            else:
                rows.append({"value": row})
        return rows

    async def __aenter__(self) -> CouchbaseConnector:
        res = await self.connect()
        if not res.success:
            raise RuntimeError(f"Couchbase connection failed: {res.message}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.disconnect()
