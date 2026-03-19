"""
In-memory Prometheus-style metrics for DB Analyzer AI v7.
Thread-safe with Lock; uses defaultdict for counters.
"""

from __future__ import annotations

import collections
import threading
import time
from typing import DefaultDict

_lock = threading.Lock()

# path -> status_code -> count
_request_counts: DefaultDict[str, DefaultDict[int, int]] = collections.defaultdict(
    lambda: collections.defaultdict(int)
)

# path -> list of duration samples (seconds)
_request_durations: DefaultDict[str, list[float]] = collections.defaultdict(list)

# run_type -> success -> count
_pipeline_counts: DefaultDict[str, DefaultDict[bool, int]] = collections.defaultdict(
    lambda: collections.defaultdict(int)
)

# run_type -> list of duration samples (seconds)
_pipeline_durations: DefaultDict[str, list[float]] = collections.defaultdict(list)


_MAX_DURATION_SAMPLES = 1000


def record_request(path: str, status_code: int, duration_s: float) -> None:
    """Record an HTTP request metric."""
    with _lock:
        _request_counts[path][status_code] += 1
        durs = _request_durations[path]
        durs.append(duration_s)
        if len(durs) > _MAX_DURATION_SAMPLES:
            _request_durations[path] = durs[-_MAX_DURATION_SAMPLES:]


def record_pipeline_run(run_type: str, duration_s: float, success: bool) -> None:
    """Record a pipeline run metric."""
    with _lock:
        _pipeline_counts[run_type][success] += 1
        durs = _pipeline_durations[run_type]
        durs.append(duration_s)
        if len(durs) > _MAX_DURATION_SAMPLES:
            _pipeline_durations[run_type] = durs[-_MAX_DURATION_SAMPLES:]


def _format_label_value(v: str) -> str:
    """Escape label value for Prometheus."""
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def get_prometheus_text() -> str:
    """Return metrics in Prometheus text exposition format."""
    lines: list[str] = []
    with _lock:
        # Request counts: http_requests_total{path="...", status="..."}
        for path, by_status in _request_counts.items():
            for status_code, count in by_status.items():
                labels = f'path="{_format_label_value(path)}",status="{status_code}"'
                lines.append(f"http_requests_total{{{labels}}} {count}")

        # Request duration: http_request_duration_seconds{path="..."}
        for path, durations in _request_durations.items():
            if durations:
                labels = f'path="{_format_label_value(path)}"'
                total = sum(durations)
                count_val = len(durations)
                lines.append(f"http_request_duration_seconds_sum{{{labels}}} {total}")
                lines.append(f"http_request_duration_seconds_count{{{labels}}} {count_val}")

        # Pipeline runs: pipeline_runs_total{run_type="...", success="true|false"}
        for run_type, by_success in _pipeline_counts.items():
            for success, count in by_success.items():
                labels = f'run_type="{_format_label_value(run_type)}",success="{str(success).lower()}"'
                lines.append(f"pipeline_runs_total{{{labels}}} {count}")

        # Pipeline duration: pipeline_run_duration_seconds{run_type="..."}
        for run_type, durations in _pipeline_durations.items():
            if durations:
                labels = f'run_type="{_format_label_value(run_type)}"'
                total = sum(durations)
                count_val = len(durations)
                lines.append(f"pipeline_run_duration_seconds_sum{{{labels}}} {total}")
                lines.append(f"pipeline_run_duration_seconds_count{{{labels}}} {count_val}")

    return "\n".join(lines) + "\n" if lines else ""
