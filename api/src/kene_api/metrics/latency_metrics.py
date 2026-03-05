"""Per-endpoint HTTP latency metrics using Prometheus histograms."""

import logging
import time

from prometheus_client import REGISTRY, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shared.structured_logging import log_context

logger = logging.getLogger(__name__)

# Bucket boundaries chosen for typical web + LLM-powered endpoints:
#   fast (static/health): 0.01-0.1s
#   normal API: 0.25-1s
#   agent calls: 2.5-30s
_LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


try:
    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "route", "status_code"],
        buckets=_LATENCY_BUCKETS,
    )
except ValueError:
    # Already registered (hot reload with --reload).
    http_request_duration_seconds = REGISTRY._names_to_collectors[
        "http_request_duration_seconds"
    ]


def _normalize_route(request: Request) -> str:
    """Return the matched route pattern (e.g. ``/api/v1/chat/completions``)
    instead of the concrete path to keep label cardinality bounded."""
    if request.scope.get("route"):
        return request.scope["route"].path
    return request.url.path


class LatencyMiddleware(BaseHTTPMiddleware):
    """Record per-route request latency as a Prometheus histogram."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        route = _normalize_route(request)

        http_request_duration_seconds.labels(
            method=request.method,
            route=route,
            status_code=response.status_code,
        ).observe(duration)

        # Log slow requests (> 1s) with structured logging
        if duration > 1.0:
            logger.warning(
                "Slow HTTP request",
                extra=log_context(
                    component="http",
                    action="request",
                    duration_ms=duration * 1000,
                    extra={
                        "method": request.method,
                        "route": route,
                        "status_code": response.status_code,
                    },
                ),
            )

        return response
