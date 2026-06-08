"""Service layer for the Early Release signup gate.

Spec: docs/design/components/data-management/projects/DM-PRD-11-early-release-signup-gate.md §4.5
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from functools import lru_cache

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.early_release_models import (
    EarlyReleaseConfig,
    EarlyReleaseRedemption,
)

logger = logging.getLogger(__name__)

# Sentinel used in constant-time compare on absent/inactive/expired paths so
# a timing channel cannot distinguish "config absent" from "wrong code".  The
# value is arbitrary and fixed; it is never the real code.
_SENTINEL: str = secrets.token_hex(16)

_APP_CONFIG_COLLECTION = "app_config"
_EARLY_RELEASE_DOC_ID = "early_release"
_REDEMPTIONS_COLLECTION = "early_release_redemptions"


class EarlyReleaseConfigNotFoundError(Exception):
    """Raised when ``set_active`` is called but no config document exists.

    A kill-switch over nothing is a programming error, not a silent no-op.
    """


class EarlyReleaseService:
    """Service for managing the shared Early Release access code.

    Patterns mirror ``FeatureFlagService``:
    - ``asyncio.to_thread`` wraps every blocking Firestore call.
    - ``datetime.now(timezone.utc)`` for all server timestamps.
    - ``model_dump(mode="json")`` for Firestore-safe writes.
    - ``gcp_exceptions.AlreadyExists`` swallowed in idempotent writes.
    """

    def __init__(self, db: firestore.Client) -> None:
        self._db = db

    def _config_ref(self) -> firestore.DocumentReference:
        return self._db.collection(_APP_CONFIG_COLLECTION).document(
            _EARLY_RELEASE_DOC_ID
        )

    def _redemption_ref(self, user_id: str) -> firestore.DocumentReference:
        return self._db.collection(_REDEMPTIONS_COLLECTION).document(user_id)

    async def get_config(self) -> EarlyReleaseConfig | None:
        """Return the singleton Early Release config, or ``None`` if absent."""
        doc = await asyncio.to_thread(self._config_ref().get)
        if not doc.exists:
            return None
        return EarlyReleaseConfig.model_validate(doc.to_dict())

    async def set_code(
        self,
        code: str,
        *,
        actor_id: str,
        expires_at: datetime | None = None,
    ) -> EarlyReleaseConfig:
        """Write (or overwrite) the shared Early Release code.

        Uses ``.set()`` (full overwrite) because rotating the code intentionally
        clears any prior expiry — a partial merge would retain the old
        ``expires_at``, which is not the correct semantic for a rotation.

        ``is_active`` is always set to ``True`` on a new code so the admin
        doesn't need a second call after rotation.
        """
        now = datetime.now(timezone.utc)
        config = EarlyReleaseConfig(
            code=code,
            is_active=True,
            expires_at=expires_at,
            updated_by=actor_id,
            updated_at=now,
        )
        data = config.model_dump(mode="json")
        await asyncio.to_thread(self._config_ref().set, data)
        return config

    async def set_active(self, is_active: bool, *, actor_id: str) -> EarlyReleaseConfig:
        """Flip the kill switch without touching the code or expiry.

        Raises:
            EarlyReleaseConfigNotFoundError: if no config document exists.
                Kill-switching nothing is a programming error.
        """
        existing = await self.get_config()
        if existing is None:
            raise EarlyReleaseConfigNotFoundError(
                "Cannot set_active: no Early Release config document exists. "
                "Call set_code first."
            )
        now = datetime.now(timezone.utc)
        updated = EarlyReleaseConfig(
            code=existing.code,
            is_active=is_active,
            expires_at=existing.expires_at,
            updated_by=actor_id,
            updated_at=now,
        )
        data = updated.model_dump(mode="json")
        await asyncio.to_thread(self._config_ref().set, data)
        return updated

    async def validate(self, code: str) -> bool:
        """Return ``True`` iff the config exists, ``is_active``, not expired, and
        the submitted code exactly matches (constant-time compare).

        Always executes exactly one ``secrets.compare_digest`` call regardless of
        which branch applies, eliminating timing channels that could leak whether
        the config is absent, inactive, or expired vs. simply wrong.
        """
        config = await self.get_config()

        # Determine whether the config is in a state where a match is possible.
        valid_config = (
            config is not None
            and config.is_active
            and (
                config.expires_at is None
                or datetime.now(timezone.utc) <= config.expires_at
            )
        )

        # Encode to UTF-8 once — compare_digest requires both operands to be the
        # same type; encoding here prevents TypeError on unicode codes.
        submitted_bytes = code.encode("utf-8")
        # Compare against the real stored code only when the config is valid;
        # otherwise compare against a fixed sentinel of known length.  A single
        # unconditional compare_digest call eliminates the branch-per-failure
        # structure that makes timing analysis easier.
        sentinel_bytes = _SENTINEL.encode("utf-8")
        # config is guaranteed non-None when valid_config is True (the first
        # condition in valid_config is `config is not None`).
        stored_bytes = (
            config.code.encode("utf-8")
            if (valid_config and config is not None)
            else sentinel_bytes
        )
        match = secrets.compare_digest(submitted_bytes, stored_bytes)
        return valid_config and match

    async def record_redemption(self, *, user_id: str, email: str, org_id: str) -> None:
        """Record that ``user_id`` onboarded via the Early Release code.

        Idempotent: if a redemption record already exists for ``user_id`` the
        call is a no-op and the original ``redeemed_at`` timestamp is preserved.
        Uses ``.create()`` + swallowed ``AlreadyExists`` (mirrors
        ``FeatureFlagService.create_flag``).
        """
        redemption = EarlyReleaseRedemption(
            user_id=user_id,
            email=email,
            org_id=org_id,
            redeemed_at=datetime.now(timezone.utc),
        )
        data = redemption.model_dump(mode="json")
        try:
            await asyncio.to_thread(self._redemption_ref(user_id).create, data)
        except gcp_exceptions.AlreadyExists:
            logger.debug(
                "early_release_redemption_already_exists",
                extra={"user_id": user_id},
            )

    async def count_redemptions(self) -> int:
        """Return the total number of Early Release redemptions.

        Issues a full-collection stream — appropriate for v1 where onboard volume
        is bounded by the rate-limited validate endpoint.  Matches the ``list_flags``
        pattern in ``FeatureFlagService``.

        TODO: replace with a Firestore COUNT aggregation query
        (``collection.count().get()``) once a hard cap on redemptions is added
        or the collection size grows beyond a few thousand documents.
        """
        docs = await asyncio.to_thread(
            lambda: list(self._db.collection(_REDEMPTIONS_COLLECTION).stream())
        )
        return len(docs)


@lru_cache(maxsize=1)
def get_early_release_service() -> EarlyReleaseService:
    """Return the process-wide ``EarlyReleaseService`` singleton.

    Uses ``@lru_cache(maxsize=1)`` so the Firestore client connection pool is
    reused across all callers.  Call ``get_early_release_service.cache_clear()``
    in tests to reset the singleton between cases.
    """
    return EarlyReleaseService(db=get_firestore_client())
