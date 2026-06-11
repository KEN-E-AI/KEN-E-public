"""Unit tests for fetch_visualization_spec in chat/artifacts.py.

Reconstructs a persisted Vega-Lite chart spec from its GCS blob so the chat
history endpoint can re-render charts after a page reload / session-status
toggle. All GCS interactions are mocked; no network required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.kene_api.chat.artifacts import (
    VEGALITE_MIME,
    fetch_visualization_spec,
)
from src.kene_api.models.chat import ChatArtifactIndex

_APP = "ken_e_chatbot"
_USER = "user_1"
_SESSION = "sess_1"
_BUCKET = "ken-e-dev-files-us"
_SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
    "title": "Sessions over time",
    "data": {"values": [{"x": 1, "y": 2}]},
    "mark": "line",
    "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
}


def _index(
    *,
    bucket: str = _BUCKET,
    filename: str = "viz_sessions_20240101T120000.json",
    version: int = 0,
    mime: str = VEGALITE_MIME,
) -> ChatArtifactIndex:
    gcs_path = f"gs://{bucket}/{_APP}/{_USER}/{_SESSION}/{filename}/{version}"
    return ChatArtifactIndex(
        artifact_id="a" * 32,
        session_id=_SESSION,
        filename=filename,
        mime_type=mime,
        size_bytes=123,
        version=version,
        gcs_path=gcs_path,
        created_by_tool="create_visualization",
    )


def _patch_storage(blob_bytes: bytes | None) -> MagicMock:
    """Return a mocked storage client whose blob downloads blob_bytes."""
    blob = MagicMock()
    if blob_bytes is None:
        blob.download_as_bytes.side_effect = RuntimeError("boom")
    else:
        blob.download_as_bytes.return_value = blob_bytes
    bucket_obj = MagicMock()
    bucket_obj.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket_obj
    return client


class TestFetchVisualizationSpec:
    def test_downloads_and_parses_spec(self) -> None:
        client = _patch_storage(json.dumps(_SPEC).encode("utf-8"))
        with patch(
            "src.kene_api.chat.artifacts._get_storage_client", return_value=client
        ):
            result = fetch_visualization_spec(_index())
        assert result == _SPEC
        # Verifies the blob name is reconstructed from the gcs_path components.
        client.bucket.assert_called_once_with(_BUCKET)
        client.bucket.return_value.blob.assert_called_once_with(
            f"{_APP}/{_USER}/{_SESSION}/viz_sessions_20240101T120000.json/0"
        )

    def test_rejects_bucket_outside_allowlist(self) -> None:
        client = _patch_storage(json.dumps(_SPEC).encode("utf-8"))
        with patch(
            "src.kene_api.chat.artifacts._get_storage_client", return_value=client
        ):
            result = fetch_visualization_spec(_index(bucket="evil-bucket"))
        assert result is None
        client.bucket.assert_not_called()

    def test_returns_none_on_malformed_gcs_path(self) -> None:
        bad = _index()
        bad.gcs_path = "not-a-gcs-uri"
        assert fetch_visualization_spec(bad) is None

    def test_returns_none_on_invalid_json(self) -> None:
        client = _patch_storage(b"{not valid json")
        with patch(
            "src.kene_api.chat.artifacts._get_storage_client", return_value=client
        ):
            assert fetch_visualization_spec(_index()) is None

    def test_returns_none_on_download_error(self) -> None:
        client = _patch_storage(None)
        with patch(
            "src.kene_api.chat.artifacts._get_storage_client", return_value=client
        ):
            assert fetch_visualization_spec(_index()) is None
