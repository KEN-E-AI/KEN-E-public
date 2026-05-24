"""Thin adapter that re-exports the four ADK skill types used by the loader.

All imports from `google.adk.skills` in this codebase go through this module.
If the ADK import path changes in a future release, this is the single edit point.

ADK version pinned in api/pyproject.toml.

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §9 (ADK import-path risk)
"""

from __future__ import annotations

from google.adk.skills import Frontmatter, Resources, Script, Skill

__all__ = ["Frontmatter", "Resources", "Script", "Skill"]
