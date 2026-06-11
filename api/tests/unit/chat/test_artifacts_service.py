"""Unit tests for register_artifact in chat/artifacts.py (CH-44).

All Firestore and ToolContext interactions are mocked; no emulator required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import AlreadyExists
from src.kene_api.chat.artifacts import register_artifact
from src.kene_api.models.chat import ChatArtifactIndex

_ACCOUNT_ID = "acc_test_01"
_SESSION_ID = "sess_test_01"
_USER_ID = "user_test_01"
_APP_NAME = "ken_e_chatbot"
_BUCKET = "ken-e-dev-files-us"
_FILENAME = "report.pdf"
_MIME = "application/pdf"
_BYTES = b"PDF content here"


def _make_tool_context(
    account_id: str | None = _ACCOUNT_ID,
    session_id: str = _SESSION_ID,
    user_id: str = _USER_ID,
    app_name: str = _APP_NAME,
    bucket: str = _BUCKET,
    save_artifact_version: int = 0,
) -> MagicMock:
    ctx = MagicMock()
    ctx.save_artifact = AsyncMock(return_value=save_artifact_version)
    ctx.user_id = user_id
    ctx.session.id = session_id
    ctx.state = MagicMock()
    ctx.state.get = MagicMock(
        side_effect=lambda k, d=None: account_id if k == "account_id" else d
    )

    invocation_ctx = MagicMock()
    invocation_ctx.app_name = app_name
    artifact_service = MagicMock()
    artifact_service.bucket_name = bucket
    invocation_ctx.artifact_service = artifact_service
    ctx._invocation_context = invocation_ctx
    return ctx


def _make_content(
    data: bytes = _BYTES,
    mime_type: str = _MIME,
) -> Any:
    from google.genai.types import Blob, Part

    return Part(inline_data=Blob(data=data, mime_type=mime_type))


class TestRegisterArtifact:
    @pytest.mark.asyncio
    async def test_returns_chat_artifact_index(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with (
            patch(
                "shared.chat_artifacts._get_firestore_client"
            ) as mock_db_factory,
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            mock_db_factory.return_value = MagicMock()
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool="my_tool"
            )

        assert isinstance(result, ChatArtifactIndex)
        assert result.filename == _FILENAME
        assert result.session_id == _SESSION_ID
        assert result.created_by_tool == "my_tool"
        assert result.version == 0
        assert result.size_bytes == len(_BYTES)
        assert result.mime_type == _MIME

    @pytest.mark.asyncio
    async def test_gcs_path_matches_build_gcs_path(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool="tool"
            )

        expected_gcs = (
            f"gs://{_BUCKET}/{_APP_NAME}/{_USER_ID}/{_SESSION_ID}/{_FILENAME}/0"
        )
        assert result.gcs_path == expected_gcs

    @pytest.mark.asyncio
    async def test_save_artifact_called_with_filename_and_content(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            await register_artifact(ctx, _FILENAME, content, created_by_tool=None)

        ctx.save_artifact.assert_awaited_once_with(_FILENAME, content)

    @pytest.mark.asyncio
    async def test_no_account_id_raises_without_indexing(self) -> None:
        """account_id absent → fail loud (RuntimeError), never touch Firestore.

        The GCS blob is already written by save_artifact, so returning a
        success-shaped result would hide an unindexed orphan. We raise instead.
        """
        ctx = _make_tool_context(account_id=None)
        content = _make_content()

        with (
            patch(
                "shared.chat_artifacts._get_firestore_client"
            ) as mock_db_factory,
            patch("shared.chat_artifacts._write_artifact_batch") as mock_batch,
            pytest.raises(RuntimeError, match="no account_id"),
        ):
            await register_artifact(ctx, _FILENAME, content, created_by_tool=None)

        mock_db_factory.assert_not_called()
        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_account_id_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_tool_context(account_id=None)
        content = _make_content()

        import logging

        with (
            caplog.at_level(logging.ERROR, logger="shared.chat_artifacts"),
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
            pytest.raises(RuntimeError),
        ):
            await register_artifact(ctx, _FILENAME, content, created_by_tool=None)

        assert any("no_account_id" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_already_exists_returns_existing_row(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        existing = ChatArtifactIndex(
            artifact_id="existing_id",
            session_id=_SESSION_ID,
            filename=_FILENAME,
            mime_type=_MIME,
            size_bytes=99,
            version=0,
            gcs_path=f"gs://{_BUCKET}/{_APP_NAME}/{_USER_ID}/{_SESSION_ID}/{_FILENAME}/0",
            created_by_tool="prior_tool",
        )

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch(
                "shared.chat_artifacts._write_artifact_batch",
                side_effect=AlreadyExists("dupe"),
            ),
            patch(
                "shared.chat_artifacts._read_existing_artifact",
                return_value=existing,
            ),
        ):
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool="new_tool"
            )

        assert result == existing

    @pytest.mark.asyncio
    async def test_already_exists_with_no_doc_returns_local_index(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        import logging

        with (
            caplog.at_level(logging.WARNING, logger="shared.chat_artifacts"),
            patch("shared.chat_artifacts._get_firestore_client"),
            patch(
                "shared.chat_artifacts._write_artifact_batch",
                side_effect=AlreadyExists("dupe"),
            ),
            patch(
                "shared.chat_artifacts._read_existing_artifact", return_value=None
            ),
        ):
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool="tool"
            )

        assert isinstance(result, ChatArtifactIndex)
        assert result.filename == _FILENAME
        assert any("race_window_fallback" in r.message for r in caplog.records)
        assert not any("artifact.registered" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_successful_write_logs_registered(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        import logging

        with (
            caplog.at_level(logging.INFO, logger="shared.chat_artifacts"),
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            await register_artifact(ctx, _FILENAME, content, created_by_tool="mytool")

        assert any("artifact.registered" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_raises_value_error_for_missing_inline_data(self) -> None:
        ctx = _make_tool_context()
        from google.genai.types import Part

        content = Part(text="no inline data here")

        with pytest.raises(ValueError, match="inline_data"):
            await register_artifact(ctx, _FILENAME, content, created_by_tool=None)

    @pytest.mark.asyncio
    async def test_raises_value_error_for_empty_created_by_tool(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with pytest.raises(ValueError, match="non-empty"):
            await register_artifact(ctx, _FILENAME, content, created_by_tool="")

    def test_raises_type_error_when_created_by_tool_omitted(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with pytest.raises(TypeError):
            register_artifact(ctx, _FILENAME, content)  # type: ignore[call-arg]

    @pytest.mark.asyncio
    async def test_raises_value_error_for_pipe_in_filename(self) -> None:
        ctx = _make_tool_context()
        content = _make_content()

        with pytest.raises(ValueError, match=r"\|"):
            await register_artifact(ctx, "bad|file.pdf", content, created_by_tool=None)

    @pytest.mark.asyncio
    async def test_mime_type_fallback_from_filename(self) -> None:
        """If inline_data.mime_type is empty, guess from filename."""
        ctx = _make_tool_context()
        from google.genai.types import Blob, Part

        content = Part(inline_data=Blob(data=b"data", mime_type=None))

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result = await register_artifact(
                ctx, "document.pdf", content, created_by_tool=None
            )

        assert result.mime_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_mime_type_fallback_to_octet_stream_for_unknown_extension(
        self,
    ) -> None:
        ctx = _make_tool_context()
        from google.genai.types import Blob, Part

        content = Part(inline_data=Blob(data=b"data", mime_type=None))

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result = await register_artifact(
                ctx, "weirdfile.xyzunknown", content, created_by_tool=None
            )

        assert result.mime_type == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_bucket_fallback_uses_environment_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ctx = _make_tool_context()
        # Remove bucket_name from artifact_service so fallback is triggered
        ctx._invocation_context.artifact_service = object()

        monkeypatch.setenv("ENVIRONMENT", "staging")
        content = _make_content()

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool=None
            )

        assert "ken-e-staging-files-us" in result.gcs_path

    @pytest.mark.asyncio
    async def test_bucket_fallback_prod_uses_ken_e_files_us(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Prod's real bucket is ken-e-files-us (NOT ken-e-production-files-us) —
        # a wrong mapping silently writes prod charts to a nonexistent bucket.
        ctx = _make_tool_context()
        ctx._invocation_context.artifact_service = object()
        monkeypatch.setenv("ENVIRONMENT", "production")
        content = _make_content()

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result = await register_artifact(
                ctx, _FILENAME, content, created_by_tool=None
            )

        assert "ken-e-files-us" in result.gcs_path
        assert "ken-e-production-files-us" not in result.gcs_path

    @pytest.mark.asyncio
    async def test_artifact_id_is_deterministic(self) -> None:
        ctx_a = _make_tool_context()
        ctx_b = _make_tool_context()
        content = _make_content()

        with (
            patch("shared.chat_artifacts._get_firestore_client"),
            patch("shared.chat_artifacts._write_artifact_batch"),
        ):
            result_a = await register_artifact(
                ctx_a, _FILENAME, content, created_by_tool=None
            )
            result_b = await register_artifact(
                ctx_b, _FILENAME, content, created_by_tool=None
            )

        assert result_a.artifact_id == result_b.artifact_id

    @pytest.mark.asyncio
    async def test_transient_firestore_error_propagates_without_success_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A transient Firestore error surviving retries must propagate.

        The GCS blob is already written, so swallowing the error would leave a
        blob with no index row while reporting success. We re-raise and never
        emit "artifact.registered".
        """
        from google.api_core.exceptions import ServiceUnavailable

        ctx = _make_tool_context()
        content = _make_content()

        import logging

        with (
            caplog.at_level(logging.INFO, logger="shared.chat_artifacts"),
            patch("shared.chat_artifacts._get_firestore_client"),
            patch(
                "shared.chat_artifacts._write_artifact_batch",
                side_effect=ServiceUnavailable("backend unavailable"),
            ),
            pytest.raises(ServiceUnavailable),
        ):
            await register_artifact(ctx, _FILENAME, content, created_by_tool="tool")

        assert not any("artifact.registered" in r.message for r in caplog.records)


class TestWriteArtifactBatchRetry:
    """Direct tests for the manual retry loop that replaced the backoff decorator
    (dropped so the Agent Engine runtime doesn't need the backoff dependency)."""

    def _db_with_commit(self, side_effects: list[Any]) -> MagicMock:
        """Firestore client whose batch.commit() applies the given side effects."""
        from google.cloud import firestore  # noqa: F401  (Increment used in code)

        batch = MagicMock()
        commit = MagicMock(side_effect=side_effects)
        batch.commit = commit
        db = MagicMock()
        db.batch.return_value = batch
        return db

    def test_retries_transient_then_succeeds(self) -> None:
        from google.api_core.exceptions import ServiceUnavailable

        from shared.chat_artifacts import _write_artifact_batch

        db = self._db_with_commit(
            [ServiceUnavailable("blip"), ServiceUnavailable("blip"), None]
        )
        with patch("shared.chat_artifacts.time.sleep"):
            _write_artifact_batch(db, _ACCOUNT_ID, _SESSION_ID, {"k": "v"}, "aid")

        # Succeeded on the 3rd attempt — committed exactly 3 times.
        assert db.batch.return_value.commit.call_count == 3

    def test_exhausts_retries_then_raises(self) -> None:
        from google.api_core.exceptions import ServiceUnavailable

        from shared.chat_artifacts import _write_artifact_batch

        db = self._db_with_commit([ServiceUnavailable("down")] * 3)
        with (
            patch("shared.chat_artifacts.time.sleep"),
            pytest.raises(ServiceUnavailable),
        ):
            _write_artifact_batch(db, _ACCOUNT_ID, _SESSION_ID, {"k": "v"}, "aid")

        assert db.batch.return_value.commit.call_count == 3

    def test_already_exists_not_retried(self) -> None:
        from shared.chat_artifacts import _write_artifact_batch

        db = self._db_with_commit([AlreadyExists("dup")])
        with (
            patch("shared.chat_artifacts.time.sleep"),
            pytest.raises(AlreadyExists),
        ):
            _write_artifact_batch(db, _ACCOUNT_ID, _SESSION_ID, {"k": "v"}, "aid")

        # AlreadyExists is non-retryable — committed exactly once.
        assert db.batch.return_value.commit.call_count == 1
