from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class RequestMetrics:
    """Aggregate upstream timing for one API request.

    The object intentionally carries counts and durations only. URLs, headers,
    tokens, query parameters, and response data never enter this context.
    """

    supabase_calls: int = 0
    auth_calls: int = 0
    postgrest_reads: int = 0
    postgrest_writes: int = 0
    supabase_elapsed_ms: float = 0.0


_current_metrics: ContextVar[RequestMetrics | None] = ContextVar(
    "supply_planning_request_metrics",
    default=None,
)


@contextmanager
def collect_request_metrics() -> Iterator[RequestMetrics]:
    metrics = RequestMetrics()
    token = _current_metrics.set(metrics)
    try:
        yield metrics
    finally:
        _current_metrics.reset(token)


def record_supabase_call(*, kind: str, method: str, elapsed_ms: float) -> None:
    metrics = _current_metrics.get()
    if metrics is None:
        return
    metrics.supabase_calls += 1
    metrics.supabase_elapsed_ms += elapsed_ms
    if kind == "auth":
        metrics.auth_calls += 1
    elif method.upper() == "GET":
        metrics.postgrest_reads += 1
    else:
        metrics.postgrest_writes += 1
