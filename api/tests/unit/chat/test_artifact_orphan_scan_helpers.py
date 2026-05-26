"""Unit tests for pure helpers in kene_api.chat.artifact_orphan_scan.

Tests cover _classify_blob, _emit_orphan_alert, _emit_completion_log,
and the _FIRESTORE_ID_RE constant.  No Firestore, GCS, or network calls
are made.
"""

from __future__ import annotations

import logging
import os
import sys
from unittest.mock import MagicMock

# Resolve the api/src package so the test runner finds kene_api.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat import artifact_orphan_scan as cli

# ---------------------------------------------------------------------------
# _classify_blob
# ---------------------------------------------------------------------------


class TestClassifyBlob:
    """Tests for _classify_blob pure function."""

    def test_no_account_id_returns_missing_session(self):
        result = cli._classify_blob(account_id=None, artifact_doc_exists=False)
        assert result == cli.CLASS_MISSING_SESSION

    def test_no_account_id_with_artifact_exists_still_returns_missing_session(self):
        # account_id=None means the session side-table row is absent; the
        # artifact_doc_exists flag is irrelevant in that case.
        result = cli._classify_blob(account_id=None, artifact_doc_exists=True)
        assert result == cli.CLASS_MISSING_SESSION

    def test_account_id_set_no_artifact_returns_missing_metadata(self):
        result = cli._classify_blob(account_id="acc_test", artifact_doc_exists=False)
        assert result == cli.CLASS_MISSING_METADATA

    def test_account_id_set_artifact_exists_returns_all_clean(self):
        result = cli._classify_blob(account_id="acc_test", artifact_doc_exists=True)
        assert result == cli.CLASS_ALL_CLEAN

    def test_empty_string_account_id_with_no_artifact_returns_missing_metadata(self):
        # An empty string is a resolved (non-None) account_id edge case.
        result = cli._classify_blob(account_id="", artifact_doc_exists=False)
        assert result == cli.CLASS_MISSING_METADATA

    def test_empty_string_account_id_with_artifact_returns_all_clean(self):
        result = cli._classify_blob(account_id="", artifact_doc_exists=True)
        assert result == cli.CLASS_ALL_CLEAN


# ---------------------------------------------------------------------------
# _emit_orphan_alert
# ---------------------------------------------------------------------------


class TestEmitOrphanAlert:
    """Tests for _emit_orphan_alert structured-log alert helper."""

    def test_emits_exactly_one_error(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_orphan_alert(
            cli.CLASS_MISSING_METADATA,
            ["path/to/blob"],
            1,
            log=mock_log,
        )
        assert mock_log.error.call_count == 1

    def test_pageable_flag_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_orphan_alert(
            cli.CLASS_MISSING_SESSION,
            ["path/a", "path/b"],
            2,
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("pageable") is True

    def test_alert_kind_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_orphan_alert(
            cli.CLASS_MISSING_METADATA,
            ["path/x"],
            1,
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("alert_kind") == "chat.orphan_scan.gcs_blob_orphan"

    def test_orphan_class_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_orphan_alert(
            cli.CLASS_MISSING_METADATA,
            ["path/x"],
            1,
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("orphan_class") == cli.CLASS_MISSING_METADATA

    def test_total_count_uses_passed_value_not_list_length(self):
        """total_count is taken from the caller, not derived from len(sample_paths)."""
        mock_log = MagicMock(spec=logging.Logger)
        paths = [f"path/{i}" for i in range(3)]
        cli._emit_orphan_alert(cli.CLASS_MISSING_SESSION, paths, 999, log=mock_log)
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("total_count") == 999

    def test_sample_paths_truncated_to_max_by_function(self):
        """The function itself still truncates sample_paths as a safety net."""
        mock_log = MagicMock(spec=logging.Logger)
        paths = [f"path/{i}" for i in range(cli._MAX_SAMPLE_PATHS + 5)]
        cli._emit_orphan_alert(
            cli.CLASS_MISSING_METADATA, paths, len(paths), log=mock_log
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert len(json_fields.get("sample_paths", [])) == cli._MAX_SAMPLE_PATHS

    def test_sample_paths_exact_match_when_under_limit(self):
        mock_log = MagicMock(spec=logging.Logger)
        paths = ["path/a", "path/b"]
        cli._emit_orphan_alert(cli.CLASS_MISSING_METADATA, paths, 2, log=mock_log)
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("sample_paths") == paths

    def test_uses_module_logger_when_none_provided(self):
        """Falls back to module-level logger without raising."""
        cli._emit_orphan_alert(cli.CLASS_MISSING_SESSION, ["path/z"], 1, log=None)


# ---------------------------------------------------------------------------
# _emit_completion_log
# ---------------------------------------------------------------------------


class TestEmitCompletionLog:
    """Tests for _emit_completion_log structured-log helper."""

    def _summary(self, **overrides: int) -> dict:
        base = {
            "scanned_blobs": 10,
            "missing_metadata": 0,
            "missing_session": 0,
            "malformed_paths": 0,
            "duration_ms": 1234,
            "errored": 0,
        }
        base.update(overrides)
        return base

    def test_emits_info_level(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(), log=mock_log)
        mock_log.info.assert_called_once()

    def test_success_true_when_no_errors(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(errored=0), log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("success") is True

    def test_success_false_when_errored(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(errored=3), log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("success") is False

    def test_all_summary_keys_present(self):
        mock_log = MagicMock(spec=logging.Logger)
        summary = self._summary(
            scanned_blobs=50,
            missing_metadata=4,
            missing_session=2,
            malformed_paths=1,
            duration_ms=5678,
            errored=0,
        )
        cli._emit_completion_log(summary, log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields["scanned_blobs"] == 50
        assert json_fields["missing_metadata"] == 4
        assert json_fields["missing_session"] == 2
        assert json_fields["malformed_paths"] == 1
        assert json_fields["duration_ms"] == 5678
        assert json_fields["errored"] == 0

    def test_uses_module_logger_when_none_provided(self):
        """Falls back to module-level logger without raising."""
        cli._emit_completion_log(self._summary(), log=None)


# ---------------------------------------------------------------------------
# _FIRESTORE_ID_RE — boundary tests
# ---------------------------------------------------------------------------


class TestFirestoreIdRegex:
    """Boundary tests for the _FIRESTORE_ID_RE constant."""

    def test_valid_account_id_passes(self):
        assert cli._FIRESTORE_ID_RE.match("acc_abc123")

    def test_id_with_slash_fails(self):
        assert not cli._FIRESTORE_ID_RE.match("bad/account/id")

    def test_id_with_double_dot_fails(self):
        assert not cli._FIRESTORE_ID_RE.match("..")

    def test_max_length_128_accepted(self):
        assert cli._FIRESTORE_ID_RE.match("a" * 128)

    def test_length_129_rejected(self):
        assert not cli._FIRESTORE_ID_RE.match("a" * 129)

    def test_empty_string_rejected(self):
        assert not cli._FIRESTORE_ID_RE.match("")

    def test_session_id_with_path_traversal_fails(self):
        assert not cli._FIRESTORE_ID_RE.match("sess/../evil")

    def test_underscore_and_dash_accepted(self):
        assert cli._FIRESTORE_ID_RE.match("acc_123-test")
