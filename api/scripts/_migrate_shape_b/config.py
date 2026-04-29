"""MigrateConfig — per-resource migration specification for migrate_to_shape_b.py."""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MigrateConfig:
    """Specification for migrating one Firestore resource from Shape A to Shape B.

    Shape A: ``{old_prefix}{account_id}/`` (top-level collection per account)
    Shape B: ``accounts/{account_id}/{new_subcollection}/`` (subcollection)

    Fields
    ------
    old_prefix:
        Prefix stripped from the source collection name to extract ``account_id``.
        For example ``"strategy_docs_"`` → collection ``strategy_docs_acc_123``
        yields ``account_id="acc_123"``.
        **May be empty** only when ``source_is_single_collection=True`` (DM-PRD-04)
        or ``is_field_migration=True`` (DM-PRD-07).
    new_subcollection:
        Destination subcollection name under ``accounts/{account_id}/``.
        Always required.
    has_versions:
        If ``True``, the runner also copies ``{doc_id}/versions/{n}`` sub-docs.
    account_id_extractor:
        Optional callable ``(collection_name: str) -> str`` that overrides the
        default prefix-stripping logic.  Required when the collection-name
        pattern is irregular (e.g. ``performance_profiles_acc_{id}``).
    source_is_single_collection:
        If ``True``, the *source* is a single global collection whose document
        IDs **are** the ``account_id`` values (DM-PRD-04 use-case for
        ``monitoring_topics`` / ``alert_configurations``).
    destination_doc_id:
        If set, all migrated docs land at
        ``accounts/{account_id}/{new_subcollection}/{destination_doc_id}``.
        Default (``None``) preserves the source document ID.
    is_field_migration:
        If ``True``, the runner walks source field paths on existing docs rather
        than moving collections (DM-PRD-07 ``members_migration`` use-case).
        The resource must register its own migration class alongside this entry.
    """

    old_prefix: str
    new_subcollection: str
    has_versions: bool = False
    account_id_extractor: Callable[[str], str] | None = field(
        default=None, compare=False, hash=False
    )
    source_is_single_collection: bool = False
    destination_doc_id: str | None = None
    is_field_migration: bool = False

    def __post_init__(self) -> None:
        if not self.new_subcollection:
            raise ValueError("new_subcollection must not be empty")
        if (
            not self.old_prefix
            and not self.source_is_single_collection
            and not self.is_field_migration
        ):
            raise ValueError(
                "old_prefix must not be empty unless source_is_single_collection=True"
                " or is_field_migration=True"
            )
