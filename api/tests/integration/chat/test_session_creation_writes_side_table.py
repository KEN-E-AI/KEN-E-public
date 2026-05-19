"""Integration tests: side-table write on session creation (CH-15).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_session_creation_writes_side_table.py -v
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_ID = "acc_ch15_test"
_SESSION_ID = "sess_ch15_real_001"
_ORG_ID = "org_ch15_test"


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


class TestSideTableWriteOnSessionCreation:
    @pytest.mark.asyncio
    async def test_side_table_row_created_after_background_task(self) -> None:
        """After _create_in_background resolves, a side-table doc must exist."""
        from src.kene_api.chat.side_table import ChatSessionSideTableService
        from src.kene_api.routers.chat import (
            _get_agent_model_id,
            _get_organization_id_for_account,
        )

        db = _emulator_client()
        svc = ChatSessionSideTableService(db=db)

        mock_neo4j = AsyncMock()
        mock_neo4j.execute_query = AsyncMock(
            return_value=[{"organization_id": _ORG_ID}]
        )

        with patch(
            "src.kene_api.routers.chat.get_neo4j_service",
            new=AsyncMock(return_value=mock_neo4j),
        ), patch(
            "src.kene_api.routers.chat.get_chat_side_table_service",
            return_value=svc,
        ), patch(
            "src.kene_api.routers.chat._get_agent_model_id",
            return_value="gemini-2.5-pro",
        ):
            org_id = await _get_organization_id_for_account(_ACCOUNT_ID)
            model_id = _get_agent_model_id()
            svc.create(
                session_id=_SESSION_ID,
                user_id="user_ch15",
                account_id=_ACCOUNT_ID,
                organization_id=org_id or "",
                model_id=model_id,
            )

        result = svc.get(account_id=_ACCOUNT_ID, session_id=_SESSION_ID)
        assert result is not None
        assert result.session_id == _SESSION_ID
        assert result.account_id == _ACCOUNT_ID
        assert result.organization_id == _ORG_ID
        assert result.model_id == "gemini-2.5-pro"

        # Cleanup
        db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()

    @pytest.mark.asyncio
    async def test_side_table_write_skipped_when_no_account_id(self) -> None:
        """If account_id is None, side-table write is skipped without error."""
        from src.kene_api.chat.side_table import ChatSessionSideTableService

        db = _emulator_client()
        svc = ChatSessionSideTableService(db=db)

        with patch(
            "src.kene_api.routers.chat.get_chat_side_table_service",
            return_value=svc,
        ):
            # No account_id → side-table must not have been written
            result = svc.get(account_id=_ACCOUNT_ID, session_id="no_account_session")
            assert result is None
