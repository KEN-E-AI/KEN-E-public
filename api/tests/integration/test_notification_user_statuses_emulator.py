"""Emulator-backed tests for notification user-status reads.

These tests run against the real Firestore client (via the emulator) rather
than mocks, because the bug they guard against — a ``__key__`` / document-id
``in`` filter rejecting plain string values with
``400 __key__ filter value must be a Key`` — only manifests against real
Firestore semantics. Mock-based tests accept the invalid filter silently,
which is exactly how the bug reached production.
"""

import os

import pytest
from google.cloud import firestore
from src.kene_api.models.kene_models import NotificationStatus
from src.kene_api.repositories import FirestoreNotificationRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firestore emulator",
)


@pytest.fixture
def db() -> firestore.Client:
    return firestore.Client(project="ken-e-test")


@pytest.fixture
def repository(db: firestore.Client) -> FirestoreNotificationRepository:
    return FirestoreNotificationRepository(db)


def _seed_status(
    db: firestore.Client, user_id: str, notification_id: str, status: NotificationStatus
) -> None:
    """Write a notification_status doc directly (test precondition)."""
    db.collection("users").document(user_id).collection("notification_status").document(
        notification_id
    ).set({"notification_id": notification_id, "status": status.value})


@pytest.mark.asyncio
async def test_get_user_statuses_returns_statuses_for_existing_notifications(
    repository: FirestoreNotificationRepository, db: firestore.Client
) -> None:
    """Reading statuses for real notification IDs must not raise.

    Regression for ``400 __key__ filter value must be a Key`` — the GET
    /notifications 500 that hid every notification from users whenever they
    actually had one to display.
    """
    user_id = "user_emulator_1"
    notification_ids = [f"notif_{i}" for i in range(3)]

    for nid in notification_ids:
        _seed_status(db, user_id, nid, NotificationStatus.READ)

    statuses = await repository.get_user_statuses(user_id, notification_ids)

    assert {nid: statuses[nid]["status"] for nid in notification_ids} == dict.fromkeys(
        notification_ids, NotificationStatus.READ.value
    )


@pytest.mark.asyncio
async def test_get_user_statuses_handles_more_than_ten_ids(
    repository: FirestoreNotificationRepository, db: firestore.Client
) -> None:
    """The read must work beyond Firestore's 10-element ``in`` limit."""
    user_id = "user_emulator_2"
    notification_ids = [f"bulk_{i}" for i in range(25)]

    for nid in notification_ids:
        _seed_status(db, user_id, nid, NotificationStatus.UNREAD)

    statuses = await repository.get_user_statuses(user_id, notification_ids)

    assert len(statuses) == 25


@pytest.mark.asyncio
async def test_get_user_statuses_empty_returns_empty(
    repository: FirestoreNotificationRepository,
) -> None:
    statuses = await repository.get_user_statuses("user_emulator_3", [])
    assert statuses == {}


@pytest.mark.asyncio
async def test_get_user_statuses_omits_ids_without_a_status_doc(
    repository: FirestoreNotificationRepository, db: firestore.Client
) -> None:
    """IDs without a status doc are absent from the result, not sentinel rows.

    This is the common production path: statuses are created lazily, so most
    requested IDs have no doc yet. ``get_all`` returns a non-existent snapshot
    for those; the ``if doc.exists`` guard must drop them so callers can apply
    their "missing == unread" default.
    """
    user_id = "user_emulator_6"
    _seed_status(db, user_id, "seeded", NotificationStatus.READ)

    statuses = await repository.get_user_statuses(
        user_id, ["seeded", "missing_a", "missing_b"]
    )

    assert set(statuses) == {"seeded"}


@pytest.mark.asyncio
async def test_update_status_creates_doc_on_first_interaction(
    repository: FirestoreNotificationRepository,
) -> None:
    """First mark-read must not 404 on the lazily-created status doc.

    Regression for ``404 no entity to update`` — statuses are created lazily,
    so a plain ``update`` failed on the user's very first read/archive action.
    """
    user_id = "user_emulator_4"
    notification_id = "fresh_notif"

    await repository.update_user_status(
        user_id, notification_id, NotificationStatus.READ
    )

    statuses = await repository.get_user_statuses(user_id, [notification_id])
    assert statuses[notification_id]["status"] == NotificationStatus.READ.value
    assert "read_at" in statuses[notification_id]


@pytest.mark.asyncio
async def test_update_status_merges_without_dropping_prior_fields(
    repository: FirestoreNotificationRepository,
) -> None:
    """A later status change must preserve fields written by earlier ones."""
    user_id = "user_emulator_5"
    notification_id = "merge_notif"

    await repository.update_user_status(
        user_id, notification_id, NotificationStatus.READ
    )
    await repository.update_user_status(
        user_id, notification_id, NotificationStatus.ARCHIVED
    )

    statuses = await repository.get_user_statuses(user_id, [notification_id])
    assert statuses[notification_id]["status"] == NotificationStatus.ARCHIVED.value
    assert "archived_at" in statuses[notification_id]
    assert "read_at" in statuses[notification_id]
