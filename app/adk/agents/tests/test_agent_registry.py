"""CI validation tests for agent registry consistency.

These tests ensure the agent registry stays in sync with the codebase.
They catch issues like missing Firestore configs, stale exports, or
duplicate entries before code reaches production.

Story: 1.16.5 - Add Agent Registry CI Validation Tests
"""

from collections import Counter
from pathlib import Path

import pytest

from .. import _EXPORT_TO_REGISTRY
from .. import __all__ as agents_all
from ..registry import get_registry


@pytest.fixture()
def registry():
    """Module-level singleton registry."""
    return get_registry()


class TestAgentRegistryCIValidation:
    """CI validation tests for the agent registry.

    Each test validates a consistency invariant between the registry
    and the rest of the codebase.
    """

    def test_no_duplicate_agent_names(self, registry):
        """Every registered agent name must be unique."""
        names = [entry.name for entry in registry.list_agents()]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        assert duplicates == [], f"Duplicate agent names: {duplicates}"

    def test_no_duplicate_config_doc_ids(self, registry):
        """Every config_doc_id must be unique across all agents (excluding None)."""
        all_ids = []
        for entry in registry.list_agents():
            if entry.config_doc_id is not None:
                all_ids.append(entry.config_doc_id)
            all_ids.extend(entry.sub_config_doc_ids)

        duplicates = [cid for cid, count in Counter(all_ids).items() if count > 1]
        assert duplicates == [], f"Duplicate config_doc_ids: {duplicates}"

    def test_allowed_config_ids_matches_registry(self, registry):
        """ALLOWED_CONFIG_IDS in the API router must equal the registry-derived set.

        The API router at api/src/kene_api/routers/agent_configs.py defines
        ALLOWED_CONFIG_IDS = get_registry().get_all_config_doc_ids(). This test
        verifies that import still produces the same set.
        """
        try:
            from api.src.kene_api.routers.agent_configs import ALLOWED_CONFIG_IDS
        except ImportError:
            pytest.skip("API router not importable (missing dependencies)")

        registry_ids = registry.get_all_config_doc_ids()
        assert ALLOWED_CONFIG_IDS == registry_ids, (
            f"ALLOWED_CONFIG_IDS out of sync.\n"
            f"  In router but not registry: {ALLOWED_CONFIG_IDS - registry_ids}\n"
            f"  In registry but not router: {registry_ids - ALLOWED_CONFIG_IDS}"
        )

    def test_exported_names_resolvable_via_registry(self, registry):
        """Every name in __init__.py's _EXPORT_TO_REGISTRY must resolve via the registry.

        Adapted from AC #5 (is_top_level agents in __all__). Since is_top_level
        doesn't exist, we verify that every exported name maps to a valid
        registry entry or alias, and every __all__ name has an export mapping.
        """
        for export_name, registry_name in _EXPORT_TO_REGISTRY.items():
            resolved = registry._aliases.get(registry_name, registry_name)
            entries = {e.name for e in registry.list_agents()}
            assert resolved in entries, (
                f"Export {export_name!r} -> registry name {registry_name!r} "
                f"(resolved: {resolved!r}) not found in registry entries: {sorted(entries)}"
            )

        unexported = [name for name in agents_all if name not in _EXPORT_TO_REGISTRY]
        assert unexported == [], (
            f"Names in __all__ but not in _EXPORT_TO_REGISTRY: {unexported}"
        )

    def test_strategy_sub_agents_have_config_doc_ids(self, registry):
        """Strategy researcher and formatter sub-agents must have config_doc_ids.

        Adapted from AC #6 (STRATEGY_RESEARCHER/FORMATTER have config_doc_id).
        Since those enums don't exist, we verify that the strategy agent's
        sub_config_doc_ids include both researcher and formatter entries.
        """
        strategy_entries = [
            e
            for e in registry.list_agents()
            if "strategy" in e.capabilities or "strategy" in e.name
        ]
        assert strategy_entries, "No strategy agent found in registry"

        for entry in strategy_entries:
            if not entry.sub_config_doc_ids:
                continue

            researcher_ids = [
                cid for cid in entry.sub_config_doc_ids if "researcher" in cid
            ]
            formatter_ids = [
                cid for cid in entry.sub_config_doc_ids if "formatter" in cid
            ]

            assert researcher_ids, (
                f"Strategy agent {entry.name!r} has sub_config_doc_ids but "
                f"none contain 'researcher': {entry.sub_config_doc_ids}"
            )
            assert formatter_ids, (
                f"Strategy agent {entry.name!r} has sub_config_doc_ids but "
                f"none contain 'formatter': {entry.sub_config_doc_ids}"
            )

            for cid in researcher_ids + formatter_ids:
                assert cid.strip(), (
                    f"Strategy agent {entry.name!r} has empty/whitespace "
                    f"config_doc_id in sub_config_doc_ids"
                )

    def test_no_empty_descriptions(self, registry):
        """Every registry entry must have a non-empty description."""
        empty = [
            entry.name
            for entry in registry.list_agents()
            if not entry.description or not entry.description.strip()
        ]
        assert empty == [], f"Agents with empty descriptions: {empty}"

    def test_module_paths_are_valid(self, registry):
        """Every module_path must point to an existing Python module on disk.

        Checks file existence directly to avoid triggering heavy module-level
        imports (agent initialization, MCP connections, env var requirements).
        """
        agents_dir = Path(__file__).parent.parent

        invalid = []
        for entry in registry.list_agents():
            # Convert relative module path to filesystem path
            # e.g. ".ken_e_agent" → "ken_e_agent.py" or "ken_e_agent/__init__.py"
            # e.g. ".company_news_chatbot.agent" → "company_news_chatbot/agent.py"
            rel_parts = entry.module_path.lstrip(".").split(".")
            candidate = agents_dir / "/".join(rel_parts)

            is_file = candidate.with_suffix(".py").is_file()
            is_package = (candidate / "__init__.py").is_file()

            if not (is_file or is_package):
                invalid.append(f"{entry.name}: {entry.module_path}")

        assert invalid == [], "Agents with unresolvable module_path:\n" + "\n".join(
            f"  - {i}" for i in invalid
        )
