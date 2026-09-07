"""
Observability module: lightweight metrics & tracing for Manual Processor.

Provides Prometheus-style metrics counters/histograms without requiring
an external OpenTelemetry collector. Designed to be optional: if the
``prometheus_client`` package is unavailable, all helpers become no-ops.

Typical usage:
    from src.observability import metrics

    with metrics.job_timer("pdf_generate"):
        generate_pdf(...)

    metrics.jobs_total.labels(status="success").inc()
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    _HAS_PROM = True
except ImportError:
    _HAS_PROM = False
    CollectorRegistry = None  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


_REGISTRY: Optional["CollectorRegistry"] = None


def get_registry() -> Optional["CollectorRegistry"]:
    """Return the process-local Prometheus registry, creating it lazily."""
    global _REGISTRY
    if not _HAS_PROM:
        return None
    if _REGISTRY is None:
        _REGISTRY = CollectorRegistry()
        _register_default_metrics(_REGISTRY)
    return _REGISTRY


def _register_default_metrics(registry: "CollectorRegistry") -> None:
    """Register the default metrics used across the application."""
    metrics.jobs_total = Counter(  # type: ignore[attr-defined]
        "manual_processor_jobs_total",
        "Number of manual-processing jobs handled, partitioned by stage and status.",
        labelnames=("stage", "status"),
        registry=registry,
    )
    metrics.job_duration_seconds = Histogram(  # type: ignore[attr-defined]
        "manual_processor_job_duration_seconds",
        "Time taken to complete a manual-processing job, in seconds.",
        labelnames=("stage",),
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
        registry=registry,
    )
    metrics.api_errors_total = Counter(  # type: ignore[attr-defined]
        "manual_processor_api_errors_total",
        "Number of errors raised by external API calls.",
        labelnames=("api",),
        registry=registry,
    )


class _MetricsNamespace:
    """Container that exposes metric helpers but tolerates a missing backend."""

    @property
    def enabled(self) -> bool:
        return _HAS_PROM and get_registry() is not None

    def record_success(self, stage: str) -> None:
        if self.enabled:
            metrics.jobs_total.labels(stage=stage, status="success").inc()  # type: ignore[attr-defined]

    def record_failure(self, stage: str) -> None:
        if self.enabled:
            metrics.jobs_total.labels(stage=stage, status="failure").inc()  # type: ignore[attr-defined]

    def record_api_error(self, api: str) -> None:
        if self.enabled:
            metrics.api_errors_total.labels(api=api).inc()  # type: ignore[attr-defined]

    @contextmanager
    def job_timer(self, stage: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            metrics.job_duration_seconds.labels(stage=stage).observe(elapsed)  # type: ignore[attr-defined]

    def render(self) -> tuple[bytes, str]:
        """Render Prometheus exposition format."""
        reg = get_registry()
        if reg is None:
            return (b"# prometheus_client not installed\n", CONTENT_TYPE_LATEST)
        return (generate_latest(reg), CONTENT_TYPE_LATEST)


metrics = _MetricsNamespace()
__all__ = ["metrics", "get_registry"]