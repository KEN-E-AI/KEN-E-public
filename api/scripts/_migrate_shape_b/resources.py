"""RESOURCES registry — populated by DM-PRD-01 through DM-PRD-04 and DM-PRD-07.

Each downstream project appends one or more entries here via a pull request.
DM-PRD-01 registered the strategy-suite resources; further entries are added
by DM-PRD-02 through DM-PRD-07 as each project ships.
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

# DM-PRD-02 will add: agent_analytics, cost_aggregations, performance_profiles
# DM-PRD-03: (field migration — no entry here; uses migrate_shape_d_split.py)
# DM-PRD-04 will add: monitoring_topics, alert_configurations
# DM-PRD-07 will add: members_migration (is_field_migration=True)
