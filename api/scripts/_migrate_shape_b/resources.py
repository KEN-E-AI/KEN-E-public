"""RESOURCES registry — populated by DM-PRD-01 through DM-PRD-04 and DM-PRD-07.

Each downstream project appends one or more entries here via a pull request.
DM-PRD-00 ships this empty; no data is migrated until the downstream PRDs land.
"""

from _migrate_shape_b.config import MigrateConfig

RESOURCES: dict[str, MigrateConfig] = {
    # DM-PRD-01 will add: strategy_docs, strategy_audit, strategy_processing_state
    # DM-PRD-02 will add: agent_analytics, cost_aggregations, performance_profiles
    # DM-PRD-03 will add: (field migration — no entry here; uses migrate_shape_d_split.py)
    # DM-PRD-04 will add: monitoring_topics, alert_configurations
    # DM-PRD-07 will add: members_migration (is_field_migration=True)
}
