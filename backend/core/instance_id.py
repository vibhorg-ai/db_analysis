"""
Backend instance id set at startup. Used so the frontend can detect restarts
and clear stale in-memory state (e.g. chat session id from localStorage).
"""

_instance_id: str = ""


def set_instance_id(value: str) -> None:
    global _instance_id
    _instance_id = value


def get_instance_id() -> str:
    return _instance_id
