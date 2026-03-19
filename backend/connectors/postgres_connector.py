"""
PostgreSQL connector using asyncpg.

Direct async connection with support for DSN or individual params,
schema metadata, read-only queries, and async context manager.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg

from backend.core.config import get_settings
from .base import ConnectionResult, is_dangerous_query

logger = logging.getLogger(__name__)


class PostgresConnector:
    """Async PostgreSQL connector using asyncpg."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        host: str | None = None,
        port: int = 5432,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._conn: asyncpg.Connection | None = None

    def _resolve_dsn(self) -> str:
        """Build connection string from DSN or individual params."""
        if self._dsn:
            return self._dsn
        settings = get_settings()
        if settings.postgres_dsn:
            return settings.postgres_dsn
        user = self._user or "postgres"
        pwd = self._password or ""
        host = self._host or "localhost"
        db = self._database or "postgres"
        return f"postgresql://{user}:{pwd}@{host}:{self._port}/{db}"

    def _connection_params(self) -> dict[str, Any]:
        """Params for asyncpg.connect (DSN or host/port/user/password/database)."""
        if self._dsn:
            return {"dsn": self._dsn}
        settings = get_settings()
        if settings.postgres_dsn:
            return {"dsn": settings.postgres_dsn}
        return {
            "host": self._host or "localhost",
            "port": self._port,
            "user": self._user or "postgres",
            "password": self._password or "",
            "database": self._database or "postgres",
        }

    async def connect(self) -> ConnectionResult:
        """Connect using asyncpg. Uses timeout from config. Fetches version via SELECT version()."""
        params = self._connection_params()
        timeout = get_settings().db_connect_timeout
        try:
            self._conn = await asyncio.wait_for(
                asyncpg.connect(**params),
                timeout=float(timeout),
            )
            version = await self._conn.fetchval("SELECT version()")
            return ConnectionResult(
                success=True,
                message="Connected",
                details={"version": str(version) if version else ""},
            )
        except asyncio.TimeoutError:
            msg = f"Connection timed out after {timeout}s"
            logger.warning(msg)
            return ConnectionResult(success=False, message=msg, details={})
        except Exception as e:
            logger.exception("PostgreSQL connection failed")
            return ConnectionResult(success=False, message=str(e), details={})

    async def disconnect(self) -> None:
        """Close connection cleanly."""
        if self._conn:
            try:
                await self._conn.close()
            except Exception as e:
                logger.debug("Error closing PostgreSQL connection: %s", e)
            finally:
                self._conn = None

    async def health_check(self) -> dict[str, Any]:
        """Return dict with connected status, database name, version."""
        if not self._conn or self._conn.is_closed():
            return {"connected": False, "error": "Not connected"}
        try:
            version = await self._conn.fetchval("SELECT version()")
            database = await self._conn.fetchval("SELECT current_database()")
            return {
                "connected": True,
                "database": str(database) if database else None,
                "version": str(version) if version else None,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def execute_read_only(
        self, query: str, *args: Any, timeout: float | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Execute read-only query. Blocks dangerous DDL/DML via is_dangerous_query.
        Returns list of dicts. Uses asyncio.wait_for for timeout.
        """
        if is_dangerous_query(query):
            raise ValueError(
                "Destructive or write operations are not allowed without authorization"
            )
        if not self._conn or self._conn.is_closed():
            raise RuntimeError("Not connected; call connect() first")
        timeout_val = timeout if timeout is not None else 30.0

        async def _fetch() -> list[dict[str, Any]]:
            rows = await self._conn.fetch(query, *args, **kwargs)
            return [dict(r) for r in rows]

        return await asyncio.wait_for(_fetch(), timeout=timeout_val)

    async def fetch_schema_metadata(
        self, timeout: float = 30.0
    ) -> list[dict[str, Any]]:
        """
        Fetch tables (pg_stat_user_tables), columns (information_schema.columns),
        primary keys, foreign keys, row estimates.
        Returns list of table dicts: {table_name, name, schema, row_count,
        columns: [{name, data_type, is_nullable}], primary_key, foreign_keys:
        [{column, target_table, ref_column, relationship_type}]}
        """
        if not self._conn or self._conn.is_closed():
            raise RuntimeError("Not connected; call connect() first")

        async def _fetch() -> list[dict[str, Any]]:
            tables: list[dict[str, Any]] = []
            # Tables and row estimates from pg_stat_user_tables
            tbl_rows = await self._conn.fetch("""
                SELECT schemaname, relname, n_live_tup AS row_count
                FROM pg_stat_user_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY schemaname, relname
            """)
            for r in tbl_rows:
                schema = r["schemaname"]
                relname = r["relname"]
                full_name = f"{schema}.{relname}" if schema != "public" else relname
                tables.append({
                    "table_name": full_name,
                    "name": full_name,
                    "schema": schema,
                    "row_count": int(r["row_count"] or 0),
                    "columns": [],
                    "primary_key": None,
                    "foreign_keys": [],
                    "indexes": [],
                })

            table_key: dict[tuple[str, str], int] = {}
            for i, t in enumerate(tables):
                short = t["table_name"].split(".")[-1] if "." in t["table_name"] else t["table_name"]
                table_key[(t["schema"], short)] = i

            # Columns from information_schema.columns
            cols = await self._conn.fetch("""
                SELECT table_schema, table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name, ordinal_position
            """)
            for c in cols:
                schema, tbl = c["table_schema"], c["table_name"]
                key = (schema, tbl)
                if key not in table_key:
                    continue
                idx = table_key[key]
                tables[idx]["columns"].append({
                    "name": c["column_name"],
                    "data_type": c["data_type"],
                    "is_nullable": c["is_nullable"] == "YES",
                })

            # Primary keys (support composite)
            pks = await self._conn.fetch("""
                SELECT tc.table_schema, tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
            """)
            pk_cols: dict[tuple[str, str], list[str]] = {}
            for pk in pks:
                key = (pk["table_schema"], pk["table_name"])
                pk_cols.setdefault(key, []).append(pk["column_name"])
            for key, cols_list in pk_cols.items():
                if key in table_key:
                    tables[table_key[key]]["primary_key"] = (
                        cols_list[0] if len(cols_list) == 1 else cols_list
                    )

            # Foreign keys
            fks = await self._conn.fetch("""
                SELECT kcu.table_schema, kcu.table_name, kcu.column_name,
                       ccu.table_schema AS ref_schema, ccu.table_name AS ref_table,
                       ccu.column_name AS ref_column
                FROM information_schema.referential_constraints rc
                JOIN information_schema.key_column_usage kcu
                  ON rc.constraint_name = kcu.constraint_name
                  AND rc.constraint_schema = kcu.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON rc.unique_constraint_name = ccu.constraint_name
                  AND rc.unique_constraint_schema = ccu.constraint_schema
                WHERE kcu.table_schema NOT IN ('pg_catalog', 'information_schema')
            """)
            for fk in fks:
                key = (fk["table_schema"], fk["table_name"])
                ref_name = (
                    f"{fk['ref_schema']}.{fk['ref_table']}"
                    if fk["ref_schema"] != "public"
                    else fk["ref_table"]
                )
                if key in table_key:
                    tables[table_key[key]]["foreign_keys"].append({
                        "column": fk["column_name"],
                        "target_table": ref_name,
                        "ref_column": fk["ref_column"],
                        "relationship_type": "one_to_many",
                    })

            # Indexes (including PK-backed indexes) with column order
            idx_rows = await self._conn.fetch("""
                SELECT
                    n.nspname AS schema_name,
                    t.relname AS table_name,
                    i.relname AS index_name,
                    array_agg(a.attname ORDER BY k.ord) FILTER (WHERE a.attname IS NOT NULL) AS columns
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord)
                LEFT JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
                    AND a.attnum > 0 AND NOT a.attisdropped
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                GROUP BY n.nspname, t.relname, i.relname
            """)
            for idx in idx_rows:
                key = (idx["schema_name"], idx["table_name"])
                if key not in table_key:
                    continue
                columns = list(idx["columns"] or [])
                tables[table_key[key]].setdefault("indexes", []).append({
                    "name": idx["index_name"],
                    "index_name": idx["index_name"],
                    "columns": columns,
                })

            return tables

        return await asyncio.wait_for(_fetch(), timeout=timeout)

    async def __aenter__(self) -> PostgresConnector:
        result = await self.connect()
        if not result.success:
            raise RuntimeError(f"PostgreSQL connection failed: {result.message}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.disconnect()
