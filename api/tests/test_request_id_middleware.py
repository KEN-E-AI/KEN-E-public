"""Unit tests for RequestIdMiddleware correlation ID handling."""

import io
import logging
import uuid

import pytest
from src.kene_api.middleware.request_id import RequestIdMiddleware, get_request_id
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from shared.structured_logging import StructuredFormatter


def _echo_request_id(request: Request) -> PlainTextResponse:
    """Endpoint that returns the current request_id from contextvars."""
    return PlainTextResponse(get_request_id())


@pytest.fixture()
def client() -> TestClient:
    app = Starlette(routes=[Route("/ping", _echo_request_id)])
    app.add_middleware(RequestIdMiddleware)
    return TestClient(app)


class TestRequestIdMiddleware:
    """Tests for RequestIdMiddleware."""

    def test_auto_generates_request_id_when_header_absent(
        self, client: TestClient
    ) -> None:
        response = client.get("/ping")
        header_value = response.headers["X-Request-Id"]
        assert header_value != ""
        # Should be a valid hex UUID (32 chars)
        uuid.UUID(header_value)  # raises ValueError if invalid

    def test_passes_through_client_provided_request_id(
        self, client: TestClient
    ) -> None:
        response = client.get("/ping", headers={"X-Request-Id": "custom-id-123"})
        assert response.headers["X-Request-Id"] == "custom-id-123"

    def test_contextvars_available_inside_handler(self, client: TestClient) -> None:
        response = client.get("/ping", headers={"X-Request-Id": "ctx-test-456"})
        assert response.text == "ctx-test-456"

    def test_contextvars_auto_generated_matches_response_header(
        self, client: TestClient
    ) -> None:
        response = client.get("/ping")
        assert response.text == response.headers["X-Request-Id"]


class TestGetRequestIdOutsideContext:
    """Tests for get_request_id() outside an active request."""

    def test_returns_empty_string_outside_request(self) -> None:
        assert get_request_id() == ""


class TestRequestIdInStructuredLogs:
    """Verify that middleware and StructuredFormatter share the same ContextVar."""

    def test_structured_formatter_picks_up_middleware_request_id(self) -> None:
        captured_log: list[str] = []

        def _log_and_echo(request: Request) -> PlainTextResponse:
            handler = logging.StreamHandler(io.StringIO())
            handler.setFormatter(StructuredFormatter())
            test_logger = logging.getLogger("test_rid_integration")
            test_logger.addHandler(handler)
            test_logger.setLevel(logging.INFO)
            test_logger.info("probe")
            captured_log.append(handler.stream.getvalue())
            test_logger.removeHandler(handler)
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/log", _log_and_echo)])
        app.add_middleware(RequestIdMiddleware)
        client = TestClient(app)

        rid = "shared-ctx-test-789"
        client.get("/log", headers={"X-Request-Id": rid})

        assert len(captured_log) == 1
        assert f'"request_id": "{rid}"' in captured_log[0]
