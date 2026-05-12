"""Unit test: verify_strategy_documents_created reads from Shape B path (DM-70).

Existing tests at ``test_strategy_generation_error_handling.py`` and
``test_account_creation_simplified.py`` mock out ``verify_strategy_documents_created``
entirely at the call site, leaving the Firestore path inside the function unguarded.

This file invokes the REAL ``verify_strategy_documents_created`` with
``firestore.Client`` patched so the function's ``db.collection(...)`` calls land on a
``MagicMock``.  The key assertion is that every collection read targets
``accounts/{account_id}/strategy_docs`` — not the legacy Shape A prefix.

Note: ``strategy_tasks.py:813`` instantiates ``db = firestore.Client()`` inside the
function body, so the patch target is
``src.kene_api.tasks.strategy_tasks.firestore.Client`` (not a module-level attribute).
"""

from unittest.mock import MagicMock, call, patch

from src.kene_api.tasks.strategy_tasks import verify_strategy_documents_created

_ACCOUNT_ID = "acc_test"

# Content dict that satisfies the completeness check:
# has_keys >= 1 and len(json.dumps(content)) > 50 bytes.
_COMPLETE_CONTENT = {"summary": "a" * 60}


class TestVerifyStrategyDocumentsCreatedShapeBPath:
    """Verify verify_strategy_documents_created reads from the Shape B collection."""

    async def test_verify_reads_from_shape_b_collection(self) -> None:
        """The function calls db.collection with the Shape B path for every doc type."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "content": _COMPLETE_CONTENT,
            "status": "complete",
            "version": 1,
        }

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        with patch(
            "src.kene_api.tasks.strategy_tasks.firestore.Client",
            return_value=mock_db,
        ):
            result = await verify_strategy_documents_created(
                account_id=_ACCOUNT_ID, require_all=True
            )

        assert result is True, (
            "Expected True when all 4 strategy docs exist and are complete"
        )

        expected_collection = f"accounts/{_ACCOUNT_ID}/strategy_docs"

        # Every call to db.collection() must use the Shape B path.
        for actual_call in mock_db.collection.call_args_list:
            assert actual_call == call(expected_collection), (
                f"db.collection was called with {actual_call!r}; "
                f"expected call({expected_collection!r}). "
                "Strategy tasks path has regressed to a non-Shape-B collection."
            )

        # Exactly 4 calls — one per expected doc type.
        _EXPECTED_DOC_TYPES = [
            "business_strategy",
            "competitive_strategy",
            "marketing_strategy",
            "brand_guidelines",
        ]
        assert mock_db.collection.call_count == len(_EXPECTED_DOC_TYPES), (
            f"Expected {len(_EXPECTED_DOC_TYPES)} collection calls, "
            f"got {mock_db.collection.call_count}"
        )
