"""
YAML-based DB connection registry.
Loads from db_connections.yaml and data/custom_connections.yaml.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from urllib.parse import quote_plus

from backend.core.config import get_settings


_V5_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_env(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values."""
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replacer(match: re.Match[str]) -> str:
        name = match.group(1)
        return os.environ.get(name, match.group(0))

    return pattern.sub(replacer, value)


def _resolve_dict(obj: Any) -> Any:
    """Recursively resolve ${ENV_VAR} in dict/list/str values."""
    if isinstance(obj, dict):
        return {k: _resolve_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_dict(v) for v in obj]
    if isinstance(obj, str):
        return _resolve_env(obj)
    return obj


def _deterministic_id(name: str, engine: str, host: str, connection_string: str, database: str) -> str:
    """Generate deterministic UUID-like ID from connection attributes."""
    raw = f"{name}|{engine}|{host}|{connection_string}|{database}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


@dataclass
class Connection:
    """DB connection metadata."""

    id: str
    name: str
    engine: str
    default: bool = False
    is_custom: bool = False
    host: str = ""
    port: int = 0
    database: str = ""
    user: str = ""
    password: str = ""
    connection_string: str = ""
    bucket: str = ""
    username: str = ""

    @property
    def dsn(self) -> str:
        """Build postgresql:// URL for postgres engine."""
        if self.engine != "postgres":
            return ""
        host = self.host or "localhost"
        port = self.port or 5432
        db = self.database or ""
        usr = quote_plus(self.user or "")
        pwd = quote_plus(self.password or "")
        return f"postgresql://{usr}:{pwd}@{host}:{port}/{db}"

    def to_dict(self) -> dict[str, Any]:
        """Return connection as dict for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "engine": self.engine,
            "default": self.default,
            "is_custom": self.is_custom,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "connection_string": self.connection_string,
            "bucket": self.bucket,
            "username": self.username,
        }


class DBRegistry:
    """Thread-safe YAML-based connection registry."""

    def __init__(self) -> None:
        self._connections: list[Connection] = []
        self._by_id: dict[str, Connection] = {}
        self._lock = threading.Lock()

    def _reload(self) -> None:
        """Read both YAML files, resolve env vars, build Connection objects."""
        settings = get_settings()
        connections: list[Connection] = []

        # Pre-configured file
        config_path = _V5_ROOT / settings.db_connections_file
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = _resolve_dict(yaml.safe_load(f) or {})
            for raw in data.get("connections", []):
                conn = self._raw_to_connection(raw, is_custom=False)
                if conn:
                    connections.append(conn)

        # Custom connections file
        custom_path = _V5_ROOT / settings.data_dir / "custom_connections.yaml"
        custom_path.parent.mkdir(parents=True, exist_ok=True)
        if custom_path.exists():
            with open(custom_path, encoding="utf-8") as f:
                custom_data = _resolve_dict(yaml.safe_load(f) or {})
            for raw in custom_data.get("connections", []):
                conn = self._raw_to_connection(raw, is_custom=True)
                if conn:
                    connections.append(conn)

        self._connections = connections
        self._by_id = {c.id: c for c in connections}

    def _raw_to_connection(self, raw: dict[str, Any], is_custom: bool) -> Connection | None:
        """Build Connection from raw YAML dict."""
        name = str(raw.get("name", ""))
        engine = str(raw.get("engine", "postgres")).lower()
        if not name or not engine:
            return None

        if is_custom and "id" in raw:
            conn_id = str(raw["id"])
        elif is_custom:
            conn_id = str(uuid.uuid4())
        else:
            host = str(raw.get("host", ""))
            cs = str(raw.get("connection_string", ""))
            db = str(raw.get("database", ""))
            conn_id = _deterministic_id(name, engine, host, cs, db)

        return Connection(
            id=conn_id,
            name=name,
            engine=engine,
            default=bool(raw.get("default", False)),
            is_custom=is_custom,
            host=str(raw.get("host", "")),
            port=int(raw.get("port", 0)),
            database=str(raw.get("database", "")),
            user=str(raw.get("user", "")),
            password=str(raw.get("password", "")),
            connection_string=str(raw.get("connection_string", "")),
            bucket=str(raw.get("bucket", "")),
            username=str(raw.get("username", "")),
        )

    def list_connections(self) -> list[Connection]:
        """Return all connections."""
        with self._lock:
            self._reload()
            return list(self._connections)

    def get_connection(self, id: str) -> Connection | None:
        """Return connection by id or None."""
        with self._lock:
            self._reload()
            return self._by_id.get(id)

    def add_connection(
        self,
        *,
        name: str,
        engine: str,
        default: bool = False,
        host: str = "",
        port: int = 0,
        database: str = "",
        user: str = "",
        password: str = "",
        connection_string: str = "",
        bucket: str = "",
        username: str = "",
    ) -> Connection:
        """Create Connection and append to custom_connections.yaml atomically."""
        conn_id = str(uuid.uuid4())
        conn = Connection(
            id=conn_id,
            name=name,
            engine=engine,
            default=default,
            is_custom=True,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connection_string=connection_string,
            bucket=bucket,
            username=username,
        )
        settings = get_settings()
        custom_path = _V5_ROOT / settings.data_dir / "custom_connections.yaml"
        custom_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._reload()
            entries = [c.to_dict() for c in self._connections if c.is_custom]
            entries.append(conn.to_dict())

        out = {"connections": entries}
        fd, tmp_path = tempfile.mkstemp(suffix=".yaml", dir=str(custom_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(out, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            os.replace(tmp_path, custom_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        with self._lock:
            self._reload()
        return conn

    def remove_connection(self, id: str) -> bool:
        """Remove connection from custom file if is_custom. Return True if removed."""
        with self._lock:
            self._reload()
            conn = self._by_id.get(id)
            if not conn or not conn.is_custom:
                return False

            entries = [c.to_dict() for c in self._connections if c.is_custom and c.id != id]
            settings = get_settings()
            custom_path = _V5_ROOT / settings.data_dir / "custom_connections.yaml"

            out = {"connections": entries}
            fd, tmp_path = tempfile.mkstemp(suffix=".yaml", dir=str(custom_path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    yaml.dump(out, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                os.replace(tmp_path, custom_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            self._reload()
            return True


_registry_instance: DBRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> DBRegistry:
    """Module-level singleton for DBRegistry."""
    global _registry_instance
    with _registry_lock:
        if _registry_instance is None:
            _registry_instance = DBRegistry()
        return _registry_instance
