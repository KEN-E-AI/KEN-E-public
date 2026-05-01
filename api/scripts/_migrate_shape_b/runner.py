"""runner.py — copy + verify + orchestrate a single MigrateConfig resource.

Called by migrate_to_shape_b.py for --resource=<name> and --all.
Not a public API — do not import from outside the migration package.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore_v1 import Client  # pragma: no cover

from .config import MigrateConfig

__all__ = [
    "AccountCopyResult",
    "AccountVerifyResult",
    "CopyResult",
    "VerifyResult",
    "copy_resource",
    "dry_run_resource",
    "migrate_resource",
    "verify_resource",
]

logger = logging.getLogger(__name__)

# Maximum number of write operations per Firestore WriteBatch (SDK limit).
_BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AccountCopyResult:
    """Copy outcome for a single account."""

    account_id: str
    source_collection: str
    docs_written: int = 0


@dataclass
class CopyResult:
    """Aggregate copy outcome for an entire resource."""

    resource_name: str
    accounts: list[AccountCopyResult] = field(default_factory=list)

    @property
    def total_docs(self) -> int:
        return sum(a.docs_written for a in self.accounts)

    @property
    def source_collections_found(self) -> int:
        return len(self.accounts)


@dataclass
class AccountVerifyResult:
    """Verification outcome for a single account."""

    account_id: str
    source_count: int
    destination_count: int

    @property
    def matches(self) -> bool:
        return self.source_count == self.destination_count


@dataclass
class VerifyResult:
    """Aggregate verification outcome for an entire resource."""

    resource_name: str
    accounts: list[AccountVerifyResult] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return all(a.matches for a in self.accounts)

    @property
    def total_source(self) -> int:
        return sum(a.source_count for a in self.accounts)

    @property
    def total_destination(self) -> int:
        return sum(a.destination_count for a in self.accounts)

    @property
    def mismatches(self) -> list[AccountVerifyResult]:
        return [a for a in self.accounts if not a.matches]


@dataclass
class AccountDeleteResult:
    """Deletion outcome for a single account."""

    account_id: str
    source_collection: str
    docs_deleted: int = 0


@dataclass
class DeleteResult:
    """Aggregate deletion outcome for an entire resource."""

    resource_name: str
    accounts: list[AccountDeleteResult] = field(default_factory=list)

    @property
    def total_docs(self) -> int:
        return sum(a.docs_deleted for a in self.accounts)

    @property
    def source_collections_deleted(self) -> int:
        return len(self.accounts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_account_id(config: MigrateConfig, collection_name: str) -> str:
    """Derive account_id from a source collection name.

    Uses ``config.account_id_extractor`` when provided, otherwise strips
    ``config.old_prefix`` from the start of the collection name.
    """
    if config.account_id_extractor is not None:
        return config.account_id_extractor(collection_name)
    return collection_name.removeprefix(config.old_prefix)


def _count_collection(client: Client, path: str) -> int:
    """Return the number of documents in a collection at *path* using server-side count."""
    agg = client.collection(path).count()
    results = agg.get()
    # results is a list of lists; the count value is at results[0][0].value
    return int(results[0][0].value)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _copy_doc_and_versions(
    client: Client,
    src_doc_ref: object,
    dest_col_path: str,
    dest_doc_id: str,
    has_versions: bool,
    *,
    batch_state: list[object],
) -> int:
    """Copy one source document (and optionally its versions) to the destination.

    Uses a shared mutable *batch_state* list ``[batch, ops_list]`` so that the
    caller can flush across multiple calls without rebuilding the batch.

    Idempotency: before queuing each write, the destination doc is fetched.
    When the destination already exists the write is skipped and logged at
    DEBUG level (message contains the literal substring "already migrated" per
    PRD §4 / AC-4).  The main doc and each ``versions/{n}`` sub-doc are
    checked independently so that a run that died after writing the main doc
    but before its versions resumes cleanly.

    Returns the number of documents *newly written* this invocation (skipped
    docs do not increment the count).
    """
    batch = batch_state[0]
    pending = batch_state[1]
    written = 0

    # Read source data
    src_snap = src_doc_ref.get()  # type: ignore[union-attr]
    if not src_snap.exists:
        return 0
    src_data = src_snap.to_dict() or {}

    # Write the main doc (skip if already present at the destination)
    dest_ref = client.document(f"{dest_col_path}/{dest_doc_id}")
    dest_snap = dest_ref.get()  # type: ignore[union-attr]
    if dest_snap.exists:
        logger.debug("already migrated: %s (skipping)", dest_ref.path)
    else:
        batch.set(dest_ref, src_data)  # type: ignore[union-attr]
        pending.append(dest_ref)
        written += 1

        if len(pending) >= _BATCH_SIZE:
            batch.commit()
            batch_state[0] = client.batch()
            batch_state[1] = []
            pending = batch_state[1]

    # Copy versions subcollection if requested; each version is checked independently.
    if has_versions:
        versions_col = src_doc_ref.collection("versions")  # type: ignore[union-attr]
        for version_doc in versions_col.stream():
            v_data = version_doc.to_dict() or {}
            v_dest = client.document(
                f"{dest_col_path}/{dest_doc_id}/versions/{version_doc.id}"
            )
            v_dest_snap = v_dest.get()  # type: ignore[union-attr]
            if v_dest_snap.exists:
                logger.debug("already migrated: %s (skipping)", v_dest.path)
            else:
                batch_state[0].set(v_dest, v_data)
                batch_state[1].append(v_dest)
                written += 1

                if len(batch_state[1]) >= _BATCH_SIZE:
                    batch_state[0].commit()
                    batch_state[0] = client.batch()
                    batch_state[1] = []

    return written


def copy_resource(client: Client, name: str, config: MigrateConfig) -> CopyResult:
    """Copy all source documents for *config* to their Shape B destinations.

    Does **not** delete source collections (that is DM-5's responsibility).
    Raises ``NotImplementedError`` for ``is_field_migration=True`` resources.

    Parameters
    ----------
    client:
        Firestore synchronous client pointing at the correct project/database.
    name:
        Resource name (used for logging only).
    config:
        Migration specification.

    Returns
    -------
    CopyResult
        Per-account copy statistics.
    """
    if config.is_field_migration:
        raise NotImplementedError(
            "is_field_migration=True is owned by DM-PRD-07 (members_migration); "
            "use migrate_shape_d_split.py for DM-PRD-03 field-tree work."
        )

    result = CopyResult(resource_name=name)

    if config.source_is_single_collection:
        # DM-PRD-04 case: source is a single global collection whose doc-IDs are account_ids.
        source_col_name = config.new_subcollection  # e.g. "monitoring_topics"
        logger.info("[%s] Walking single source collection: %s", name, source_col_name)

        batch = client.batch()
        pending: list[object] = []
        batch_state = [batch, pending]

        source_col = client.collection(source_col_name)
        for src_doc in source_col.stream():
            account_id = src_doc.id  # doc-id IS the account_id
            dest_col_path = f"accounts/{account_id}/{config.new_subcollection}"
            dest_doc_id = (
                config.destination_doc_id if config.destination_doc_id else src_doc.id
            )

            acc_result = AccountCopyResult(
                account_id=account_id,
                source_collection=source_col_name,
            )
            written = _copy_doc_and_versions(
                client,
                src_doc.reference,
                dest_col_path,
                dest_doc_id,
                config.has_versions,
                batch_state=batch_state,
            )
            acc_result.docs_written = written
            result.accounts.append(acc_result)
            logger.debug("[%s] account=%s written=%d", name, account_id, written)

        # Flush remaining
        if batch_state[1]:
            batch_state[0].commit()

    else:
        # Standard case: walk collections whose names start with old_prefix.
        logger.info(
            "[%s] Scanning top-level collections with prefix '%s'",
            name,
            config.old_prefix,
        )
        batch = client.batch()
        pending_: list[object] = []
        batch_state = [batch, pending_]

        for col_ref in client.collections():
            col_name = col_ref.id
            if not col_name.startswith(config.old_prefix):
                continue

            account_id = _extract_account_id(config, col_name)
            dest_col_path = f"accounts/{account_id}/{config.new_subcollection}"

            acc_result = AccountCopyResult(
                account_id=account_id,
                source_collection=col_name,
            )

            for src_doc in col_ref.stream():
                dest_doc_id = (
                    config.destination_doc_id
                    if config.destination_doc_id
                    else src_doc.id
                )
                written = _copy_doc_and_versions(
                    client,
                    src_doc.reference,
                    dest_col_path,
                    dest_doc_id,
                    config.has_versions,
                    batch_state=batch_state,
                )
                acc_result.docs_written += written

            result.accounts.append(acc_result)
            logger.info(
                "[%s] Copied %d docs from %s → %s",
                name,
                acc_result.docs_written,
                col_name,
                dest_col_path,
            )

        # Flush remaining
        if batch_state[1]:
            batch_state[0].commit()

    return result


def verify_resource(client: Client, name: str, config: MigrateConfig) -> VerifyResult:
    """Compare per-account source vs. destination doc counts.

    Note: for ``source_is_single_collection=True``, only top-level destination
    docs are counted (not ``versions/`` sub-docs). Combine with ``has_versions=True``
    only when version verification is not required — no current resource does this.

    Returns
    -------
    VerifyResult
        Per-account counts and an overall ``verified`` flag.
    """
    if config.is_field_migration:
        raise NotImplementedError(
            "is_field_migration=True is owned by DM-PRD-07 (members_migration); "
            "use migrate_shape_d_split.py for DM-PRD-03 field-tree work."
        )

    result = VerifyResult(resource_name=name)

    if config.source_is_single_collection:
        source_col_name = config.new_subcollection
        source_col = client.collection(source_col_name)
        for src_doc in source_col.stream():
            account_id = src_doc.id
            dest_col_path = f"accounts/{account_id}/{config.new_subcollection}"
            # Source: count of this single doc (always 1 since we stream docs)
            src_count = 1
            dest_count = _count_collection(client, dest_col_path)
            result.accounts.append(
                AccountVerifyResult(
                    account_id=account_id,
                    source_count=src_count,
                    destination_count=dest_count,
                )
            )
    else:
        for col_ref in client.collections():
            col_name = col_ref.id
            if not col_name.startswith(config.old_prefix):
                continue

            account_id = _extract_account_id(config, col_name)
            dest_col_path = f"accounts/{account_id}/{config.new_subcollection}"

            src_count = _count_collection(client, col_name)
            dest_count = _count_collection(client, dest_col_path)

            result.accounts.append(
                AccountVerifyResult(
                    account_id=account_id,
                    source_count=src_count,
                    destination_count=dest_count,
                )
            )

    for mismatch in result.mismatches:
        logger.warning(
            "[%s] COUNT MISMATCH account=%s source=%d destination=%d",
            name,
            mismatch.account_id,
            mismatch.source_count,
            mismatch.destination_count,
        )

    return result


def delete_source_collections(
    client: Client, name: str, config: MigrateConfig
) -> DeleteResult:
    """Delete all source documents for *config* after a verified copy.

    Walks the same source collections used by ``copy_resource`` /
    ``verify_resource``, batch-deletes every document (and ``versions/{n}``
    sub-docs when ``has_versions=True``), and returns per-account deletion stats.

    Does **not** prompt or print — those responsibilities belong to the CLI layer.
    Raises ``NotImplementedError`` for ``is_field_migration=True`` resources (owned
    by DM-PRD-07).

    Parameters
    ----------
    client:
        Firestore synchronous client pointing at the correct project/database.
    name:
        Resource name (used for logging only).
    config:
        Migration specification.

    Returns
    -------
    DeleteResult
        Per-account deletion statistics.
    """
    if config.is_field_migration:
        raise NotImplementedError(
            "is_field_migration=True is owned by DM-PRD-07 (members_migration); "
            "delete logic for field migrations must be handled separately."
        )

    result = DeleteResult(resource_name=name)

    if config.source_is_single_collection:
        source_col_name = config.new_subcollection
        logger.info(
            "[%s] Deleting source documents from single collection: %s",
            name,
            source_col_name,
        )

        source_col = client.collection(source_col_name)
        batch = client.batch()
        pending: list[object] = []
        batch_state = [batch, pending]

        for src_doc in source_col.stream():
            account_id = src_doc.id
            acc_result = AccountDeleteResult(
                account_id=account_id,
                source_collection=source_col_name,
            )

            # Delete versions subcollection first if needed
            if config.has_versions:
                versions_col = src_doc.reference.collection("versions")
                for version_doc in versions_col.stream():
                    batch_state[0].delete(version_doc.reference)
                    batch_state[1].append(version_doc.reference)
                    acc_result.docs_deleted += 1
                    if len(batch_state[1]) >= _BATCH_SIZE:
                        batch_state[0].commit()
                        batch_state[0] = client.batch()
                        batch_state[1] = []

            # Delete the source doc itself
            batch_state[0].delete(src_doc.reference)
            batch_state[1].append(src_doc.reference)
            acc_result.docs_deleted += 1
            if len(batch_state[1]) >= _BATCH_SIZE:
                batch_state[0].commit()
                batch_state[0] = client.batch()
                batch_state[1] = []

            result.accounts.append(acc_result)
            logger.debug(
                "[%s] account=%s deleted=%d from %s",
                name,
                account_id,
                acc_result.docs_deleted,
                source_col_name,
            )

        if batch_state[1]:
            batch_state[0].commit()

    else:
        logger.info(
            "[%s] Deleting source collections with prefix '%s'",
            name,
            config.old_prefix,
        )

        batch = client.batch()
        pending_: list[object] = []
        batch_state = [batch, pending_]

        for col_ref in client.collections():
            col_name = col_ref.id
            if not col_name.startswith(config.old_prefix):
                continue

            account_id = _extract_account_id(config, col_name)
            acc_result = AccountDeleteResult(
                account_id=account_id,
                source_collection=col_name,
            )

            for src_doc in col_ref.stream():
                # Delete versions subcollection first if needed
                if config.has_versions:
                    versions_col = src_doc.reference.collection("versions")
                    for version_doc in versions_col.stream():
                        batch_state[0].delete(version_doc.reference)
                        batch_state[1].append(version_doc.reference)
                        acc_result.docs_deleted += 1
                        if len(batch_state[1]) >= _BATCH_SIZE:
                            batch_state[0].commit()
                            batch_state[0] = client.batch()
                            batch_state[1] = []

                # Delete the source doc itself
                batch_state[0].delete(src_doc.reference)
                batch_state[1].append(src_doc.reference)
                acc_result.docs_deleted += 1
                if len(batch_state[1]) >= _BATCH_SIZE:
                    batch_state[0].commit()
                    batch_state[0] = client.batch()
                    batch_state[1] = []

            result.accounts.append(acc_result)
            logger.info(
                "[%s] Deleted %d docs from %s",
                name,
                acc_result.docs_deleted,
                col_name,
            )

        if batch_state[1]:
            batch_state[0].commit()

    return result


def dry_run_resource(client: Client, name: str, config: MigrateConfig) -> int:
    """Walk source collections, count docs, and print the PRD §4 summary block.

    Does **not** write to the destination or delete any source data.
    Mirrors ``copy_resource``'s source-discovery logic so a dry-run accurately
    reflects what a real run will copy.

    Note: if the source-walk logic in ``copy_resource`` ever changes, this
    function must be updated in parallel to keep the dry-run honest.

    Returns
    -------
    int
        0 on success, 3 on unexpected runtime error.
    """
    if config.is_field_migration:
        raise NotImplementedError(
            "is_field_migration=True is owned by DM-PRD-07 (members_migration); "
            "use migrate_shape_d_split.py for DM-PRD-03 field-tree work."
        )

    try:
        source_collections_found = 0
        total_source_docs = 0

        if config.source_is_single_collection:
            # DM-PRD-04 case: single global collection whose doc-IDs are account_ids.
            source_col_name = config.new_subcollection
            logger.info(
                "[%s] dry-run: walking single source collection: %s", name, source_col_name
            )
            source_col = client.collection(source_col_name)
            # Collect account_ids in one pass to avoid a second stream() call for dest count.
            account_ids: list[str] = []
            for src_doc in source_col.stream():
                account_ids.append(src_doc.id)
                source_collections_found += 1
                # Each top-level doc represents one account; count it as 1 doc.
                total_source_docs += 1
        else:
            # Standard case: walk collections whose names start with old_prefix.
            logger.info(
                "[%s] dry-run: scanning top-level collections with prefix '%s'",
                name,
                config.old_prefix,
            )
            account_ids = []
            for col_ref in client.collections():
                col_name = col_ref.id
                if not col_name.startswith(config.old_prefix):
                    continue
                source_collections_found += 1
                src_count = _count_collection(client, col_name)
                total_source_docs += src_count
                account_ids.append(_extract_account_id(config, col_name))
                logger.debug(
                    "[%s] dry-run: found %s with %d docs", name, col_name, src_count
                )

        dest_path_sample = f"accounts/{{id}}/{config.new_subcollection}"
        # Count what's already at the destination (typically 0 on first run).
        dest_count = sum(
            _count_collection(client, f"accounts/{aid}/{config.new_subcollection}")
            for aid in account_ids
        )

        print(f"Resource: {name}")
        print(f"  Source collections found:   {source_collections_found}")
        print(f"  Source doc count:            {total_source_docs:,}")
        print(f"  Destination path:            {dest_path_sample}")
        print(f"  Destination doc count:       {dest_count:,}")
        print("  Status:                      DRY RUN")
        print("  Next step:                   re-run without --dry-run to copy")

        return 0

    except NotImplementedError:
        raise
    except Exception:
        logger.exception("[%s] Unexpected error during dry-run", name)
        return 3


def migrate_resource(client: Client, name: str, config: MigrateConfig) -> int:
    """Orchestrate copy → verify and print the PRD §4 summary block.

    Returns
    -------
    int
        Exit code: 0 = VERIFIED, 1 = FAILED, 3 = runtime error.
    """
    try:
        copy_result = copy_resource(client, name, config)
        verify_result = verify_resource(client, name, config)

        # Determine destination path template for the summary block
        dest_path_sample = f"accounts/{{id}}/{config.new_subcollection}"
        status = "VERIFIED" if verify_result.verified else "FAILED"
        next_step = (
            "re-run with --confirm-delete"
            if verify_result.verified
            else "inspect mismatches above, then re-run"
        )

        print(f"Resource: {name}")
        print(f"  Source collections found:   {copy_result.source_collections_found}")
        print(f"  Source doc count:            {verify_result.total_source:,}")
        print(f"  Destination path:            {dest_path_sample}")
        print(f"  Destination doc count:       {verify_result.total_destination:,}")
        print(f"  Status:                      {status}")
        print(f"  Next step:                   {next_step}")

        if not verify_result.verified:
            for mismatch in verify_result.mismatches:
                print(
                    f"    MISMATCH account={mismatch.account_id} "
                    f"source={mismatch.source_count} "
                    f"destination={mismatch.destination_count}",
                    file=sys.stderr,
                )
            return 1

        return 0

    except NotImplementedError:
        raise
    except Exception:
        logger.exception("[%s] Unexpected error during migration", name)
        return 3
