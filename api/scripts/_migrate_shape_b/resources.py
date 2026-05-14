"""RESOURCES registry — populated by DM-PRD-01 through DM-PRD-04 and DM-PRD-07.

Each downstream project appends one or more entries here via a pull request.
DM-PRD-01 registered the strategy-suite resources; DM-PRD-02 added the
analytics-suite resources. Further entries are added by DM-PRD-03 through
DM-PRD-07 as each project ships.
"""

from .config import MigrateConfig

RESOURCES: dict[str, MigrateConfig] = {}

# DM-PRD-01 (Strategy Suite Migration — DM-12)
RESOURCES["strategy_processing_state"] = MigrateConfig(
    old_prefix="strategy_processing_state_",
    new_subcollection="strategy_processing_state",
    has_versions=False,
)
RESOURCES["strategy_docs"] = MigrateConfig(
    old_prefix="strategy_docs_",
    new_subcollection="strategy_docs",
    has_versions=True,
)
RESOURCES["strategy_audit"] = MigrateConfig(
    old_prefix="strategy_audit_",
    new_subcollection="strategy_audit",
    has_versions=False,
)

# DM-PRD-02 (Analytics Suite Migration — DM-30)
RESOURCES["agent_analytics"] = MigrateConfig(
    old_prefix="agent_analytics_",
    new_subcollection="agent_analytics",
    has_versions=False,
)
RESOURCES["cost_aggregations"] = MigrateConfig(
    old_prefix="cost_aggregations_",
    new_subcollection="cost_aggregations",
    has_versions=False,
)
RESOURCES["performance_profiles"] = MigrateConfig(
    old_prefix="performance_profiles_",
    new_subcollection="performance_profiles",
    has_versions=False,
)

# DM-PRD-03: (field migration — no entry here; uses migrate_shape_d_split.py)

# DM-PRD-04 (Shape B-like Collapse — DM-22)
RESOURCES["alert_configurations"] = MigrateConfig(
    old_prefix="",
    new_subcollection="alert_configurations",
    has_versions=False,
    source_is_single_collection=True,
    destination_doc_id="default",
)
RESOURCES["monitoring_topics"] = MigrateConfig(
    old_prefix="",
    new_subcollection="monitoring_topics",
    has_versions=False,
    source_is_single_collection=True,
    destination_doc_id="default",
)

# DM-PRD-07 will add: members_migration (is_field_migration=True)
