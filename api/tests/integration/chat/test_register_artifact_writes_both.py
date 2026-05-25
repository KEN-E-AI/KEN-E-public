"""Integration tests: register_artifact writes both artifact index and side-table (CH-44).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_register_artifact_writes_both.py -v
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_ID = "acc_ch44_int"
_SESSION_ID = "sess_ch44_int_001"
_USER_ID = "user_ch44_int"
_APP_NAME = "ken_e_chatbot"
_BUCKET = "ken-e-test-files-us"
_FILENAME = "artifact_ch44.pdf"
_BYTES = b"fake pdf content"
_MIME = "application/pdf"


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _make_tool_context(
    account_id: str | None = _ACCOUNT_ID,
    save_version: int = 0,
) -> MagicMock:
    ctx = MagicMock()
    ctx.save_artifact = AsyncMock(return_value=save_version)
    ctx.user_id = _USER_ID
    ctx.session.id = _SESSION_ID
    ctx.state = MagicMock()
    ctx.state.get = MagicMock(
        side_effect=lambda k, d=None: account_id if k == "account_id" else d
    )

    invocation_ctx = MagicMock()
    invocation_ctx.app_name = _APP_NAME
    artifact_service = MagicMock()
    artifact_service.bucket_name = _BUCKET
    invocation_ctx.artifact_service = artifact_service
    ctx._invocation_context = invocation_ctx
    return ctx


def _seed_session(db: Any) -> None:
    doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}")
    doc.set(
        {
            "session_id": _SESSION_ID,
            "account_id": _ACCOUNT_ID,
            "user_id": _USER_ID,
            "artifact_count": 0,
            "created_at": None,
            "updated_at": None,
        }
    )


def _cleanup(db: Any, artifact_id: str) -> None:
    db.document(
        f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts/{artifact_id}"
    ).delete()
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()


class TestRegisterArtifactWritesBoth:
    @pytest.mark.asyncio
    async def test_artifact_index_row_created(self) -> None:
        from google.genai.types import Blob, Part
        from src.kene_api.chat.artifacts import _artifact_id, register_artifact

        db = _emulator_client()
        _seed_session(db)

        content = Part(inline_data=Blob(data=_BYTES, mime_type=_MIME))
        ctx = _make_tool_context()

        import src.kene_api.chat.artifacts as _artifacts_mod

        original_fn = _artifacts_mod.get_firestore_client
        _artifacts_mod.get_firestore_client = lambda: db  # type: ignore[assignment]

        art_id = _artifact_id(_SESSION_ID, _FILENAME, 0)
        try:
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool="test_tool"
            )

            # Verify artifact index written
            artifact_doc = db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts/{result.artifact_id}"
            ).get()
            assert artifact_doc.exists
            data = artifact_doc.to_dict()
            assert data["session_id"] == _SESSION_ID
            assert data["filename"] == _FILENAME
            assert data["mime_type"] == _MIME
            assert data["size_bytes"] == len(_BYTES)
            assert data["created_by_tool"] == "test_tool"
            assert data["version"] == 0

            # Verify side-table artifact_count incremented
            session_doc = db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
            ).get()
            assert session_doc.to_dict()["artifact_count"] == 1
        finally:
            _artifacts_mod.get_firestore_client = original_fn  # type: ignore[assignment]
            _cleanup(db, art_id)

    @pytest.mark.asyncio
    async def test_idempotent_second_call_does_not_double_increment(self) -> None:
        from google.genai.types import Blob, Part
        from src.kene_api.chat.artifacts import _artifact_id, register_artifact

        db = _emulator_client()
        _seed_session(db)

        content = Part(inline_data=Blob(data=_BYTES, mime_type=_MIME))
        ctx = _make_tool_context(save_version=0)

        import src.kene_api.chat.artifacts as _artifacts_mod

        original_fn = _artifacts_mod.get_firestore_client
        _artifacts_mod.get_firestore_client = lambda: db  # type: ignore[assignment]

        try:
            # First call
            await register_artifact(ctx, _FILENAME, content, created_by_tool="tool1")

            # Second call with same (session, filename, version=0) → AlreadyExists on batch.create
            ctx2 = _make_tool_context(save_version=0)
            await register_artifact(ctx2, _FILENAME, content, created_by_tool="tool2")
        finally:
            _artifacts_mod.get_firestore_client = original_fn  # type: ignore[assignment]

        # artifact_count must still be 1 — not 2
        session_doc = db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
        ).get()
        assert session_doc.to_dict()["artifact_count"] == 1

        art_id = _artifact_id(_SESSION_ID, _FILENAME, 0)
        _cleanup(db, art_id)
