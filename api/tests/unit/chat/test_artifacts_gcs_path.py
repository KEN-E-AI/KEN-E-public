"""Unit tests for GCS path pure helpers in chat/artifacts.py (CH-44)."""

from __future__ import annotations

from src.kene_api.chat.artifacts import (
    ParsedArtifactPath,
    build_gcs_path,
    parse_gcs_path,
)


class TestBuildGcsPath:
    def test_spec_example(self) -> None:
        """Exact byte-for-byte match from the Implementation Plan AC."""
        result = build_gcs_path(
            "ken_e_chatbot",
            "u1",
            "s1",
            "report.pdf",
            0,
            bucket="ken-e-artifacts-dev",
        )
        assert result == "gs://ken-e-artifacts-dev/ken_e_chatbot/u1/s1/report.pdf/0"

    def test_version_embedded_as_int(self) -> None:
        result = build_gcs_path("app", "user", "sess", "file.txt", 3, bucket="bkt")
        assert result.endswith("/3")

    def test_version_zero(self) -> None:
        result = build_gcs_path("app", "u", "s", "f", 0, bucket="b")
        assert "/0" in result

    def test_all_segments_present(self) -> None:
        result = build_gcs_path(
            "myapp", "myuser", "mysess", "myfile.csv", 7, bucket="mybucket"
        )
        assert result == "gs://mybucket/myapp/myuser/mysess/myfile.csv/7"


class TestParseGcsPath:
    def test_round_trip(self) -> None:
        original = ParsedArtifactPath(
            app_name="ken_e_chatbot",
            user_id="u1",
            session_id="sess_abc",
            filename="report.pdf",
            version=2,
        )
        path = build_gcs_path(
            original.app_name,
            original.user_id,
            original.session_id,
            original.filename,
            original.version,
            bucket="any-bucket",
        )
        parsed = parse_gcs_path(path)
        assert parsed == original

    def test_version_is_int(self) -> None:
        path = "gs://bkt/app/user/sess/file.txt/5"
        parsed = parse_gcs_path(path)
        assert parsed is not None
        assert isinstance(parsed.version, int)
        assert parsed.version == 5

    def test_returns_none_for_no_scheme(self) -> None:
        assert parse_gcs_path("bkt/app/user/sess/file/0") is None

    def test_returns_none_for_http(self) -> None:
        assert parse_gcs_path("https://storage.googleapis.com/bkt/app/u/s/f/0") is None

    def test_returns_none_for_non_integer_version(self) -> None:
        assert parse_gcs_path("gs://bkt/app/user/sess/file.txt/latest") is None

    def test_returns_none_for_too_few_segments(self) -> None:
        assert parse_gcs_path("gs://bkt/app/user/sess/file.txt") is None

    def test_returns_none_for_too_many_segments(self) -> None:
        # 7 segments after bucket → too many
        assert parse_gcs_path("gs://bkt/a/b/c/d/e/f/0") is None

    def test_spec_example_fields(self) -> None:
        path = "gs://ken-e-artifacts-dev/ken_e_chatbot/u1/s1/report.pdf/0"
        parsed = parse_gcs_path(path)
        assert parsed is not None
        assert parsed.app_name == "ken_e_chatbot"
        assert parsed.user_id == "u1"
        assert parsed.session_id == "s1"
        assert parsed.filename == "report.pdf"
        assert parsed.version == 0
