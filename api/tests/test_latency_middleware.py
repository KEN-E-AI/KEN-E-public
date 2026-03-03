"""Unit tests for LatencyMiddleware and _normalize_route."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.kene_api.metrics.latency_metrics import LatencyMiddleware, _normalize_route


def _ok_handler(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@pytest.fixture()
def client() -> TestClient:
    app = Starlette(routes=[Route("/api/v1/items/{item_id}", _ok_handler)])
    app.add_middleware(LatencyMiddleware)
    return TestClient(app)


class TestLatencyMiddleware:
    """LatencyMiddleware should observe request duration."""

    def test_records_duration_for_request(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.metrics.latency_metrics.http_request_duration_seconds"
        ) as mock_hist:
            mock_labels = MagicMock()
            mock_hist.labels.return_value = mock_labels

            response = client.get("/api/v1/items/42")

            assert response.status_code == 200
            mock_hist.labels.assert_called_once()
            call_kwargs = mock_hist.labels.call_args.kwargs
            assert call_kwargs["method"] == "GET"
            assert call_kwargs["status_code"] == 200
            mock_labels.observe.assert_called_once()
            duration = mock_labels.observe.call_args[0][0]
            assert duration > 0

    def test_records_route_label(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.metrics.latency_metrics.http_request_duration_seconds"
        ) as mock_hist:
            mock_hist.labels.return_value = MagicMock()
            client.get("/api/v1/items/42")

            call_kwargs = mock_hist.labels.call_args.kwargs
            assert "route" in call_kwargs
            assert call_kwargs["route"] != ""


class TestNormalizeRoute:
    """_normalize_route should return route pattern, not concrete path."""

    def test_returns_route_pattern_when_available(self) -> None:
        mock_route = MagicMock()
        mock_route.path = "/api/v1/users/{user_id}"
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {"route": mock_route}
        mock_request.url.path = "/api/v1/users/abc-123"

        assert _normalize_route(mock_request) == "/api/v1/users/{user_id}"

    def test_falls_back_to_url_path_when_no_route(self) -> None:
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {}
        mock_request.url.path = "/unknown/path"

        assert _normalize_route(mock_request) == "/unknown/path"
