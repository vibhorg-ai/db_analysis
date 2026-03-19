"""
Circuit breaker for AMAIZ LLM calls.

After N consecutive failures, the circuit opens for T seconds.
Thread-safe implementation using threading.Lock.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from backend.core.config import get_settings

if TYPE_CHECKING:
    pass


class CircuitOpenError(Exception):
    """Raised when the circuit is open (too many failures)."""

    def __init__(self, message: str, retry_after_seconds: int | float) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CircuitBreaker:
    """
    Tracks consecutive failures; after N failures, opens for T seconds.
    Uses record_success() / record_failure() to update state.
    check() raises CircuitOpenError if the circuit is open.
    """

    def __init__(self, failures_threshold: int | None = None, open_seconds: int | None = None) -> None:
        settings = get_settings()
        self._failures_threshold = failures_threshold if failures_threshold is not None else settings.circuit_breaker_failures
        self._open_seconds = open_seconds if open_seconds is not None else settings.circuit_breaker_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Reset failure count on success."""
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        """Increment failure count, potentially opening the circuit."""
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failures_threshold:
                self._opened_at = time.monotonic()

    def check(self) -> None:
        """
        Raise CircuitOpenError if the circuit is open.
        If closed, does nothing.
        """
        with self._lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._open_seconds:
                # Time expired; close the circuit and reset
                self._consecutive_failures = 0
                self._opened_at = None
                return
            retry_after = self._open_seconds - int(elapsed)
            raise CircuitOpenError(
                f"Circuit open: {self._consecutive_failures} failures. Retry after {retry_after}s.",
                retry_after_seconds=retry_after,
            )


_circuit: CircuitBreaker | None = None
_circuit_lock = threading.Lock()


def get_amaiz_circuit() -> CircuitBreaker:
    """Module-level singleton for the AMAIZ circuit breaker."""
    global _circuit
    with _circuit_lock:
        if _circuit is None:
            _circuit = CircuitBreaker()
        return _circuit
