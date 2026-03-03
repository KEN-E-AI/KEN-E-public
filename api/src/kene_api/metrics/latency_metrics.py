"""Per-endpoint HTTP latency metrics using Prometheus histograms."""

import time

from prometheus_client import REGISTRY, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Bucket boundaries chosen for typical web + LLM-powered endpoints:
#   fast (static/health): 0.01-0.1s
#   normal API: 0.25-1s
#   agent calls: 2.5-30s
_LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


def _get_or_create_histogram(
    name: str, documentation: str, labelnames: list[str], buckets: tuple[float, ...]
) -> Histogram:
    for collector in list(REGISTRY._collector_to_names.keys()):
        registered_names = REGISTRY._collector_to_names.get(collector, [])
        if name in registered_names:
            return collector  # type: ignore[return-value]
    try:
        return Histogram(name, documentation, labelnames, buckets=buckets)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            for collector in list(REGISTRY._collector_to_names.keys()):
                registered_names = REGISTRY._collector_to_names.get(collector, [])
                if name in registered_names:
                    return collector  # type: ignore[return-value]
        raise


http_request_duration_seconds = _get_or_create_histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route", "status_code"],
    _LATENCY_BUCKETS,
)


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

        http_request_duration_seconds.labels(
            method=request.method,
            route=_normalize_route(request),
            status_code=response.status_code,
        ).observe(duration)

        return response
