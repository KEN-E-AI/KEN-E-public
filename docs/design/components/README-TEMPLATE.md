# {Component Name} — README

## 1. Overview

{2-3 paragraphs describing what this component does, who it serves, and why it exists. Include the component's role within the broader KEN-E platform. A developer reading only this section should understand the component's purpose and boundaries.}

## 2. Architecture

### 2.1 Key Directories

{List the directories and entry points in the codebase that belong to this component. Be specific — the Dev Team agent uses these paths to find existing code before writing new code.}

| Path | Purpose |
|------|---------|
| `frontend/src/{path}/` | {What this directory contains} |
| `backend/src/{path}/` | {What this directory contains} |

### 2.2 Data Flow

{Describe how data moves through this component. Where does input come from? What transformations happen? Where does output go? Include the data store(s) this component reads from and writes to.}

### 2.3 API Contracts

{List the API endpoints this component owns or consumes. For owned endpoints, reference the Pydantic models or Zod schemas that define request/response shapes. For consumed endpoints, reference the owning component's PRD.}

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/{path}` | GET/POST | This component | `{schema file path}` |

### 2.4 Key Abstractions

{List the most important classes, hooks, contexts, or utilities that a developer must understand before modifying this component. For each, give a one-sentence description and file path. Limit to 5-10 entries — the ones that appear most frequently in import statements.}

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `{ClassName/hookName}` | `{file path}` | {One sentence} |

## 3. Component Dependencies

### 3.1 Depends On

{List other KEN-E components this component depends on. For each, describe the dependency and reference the specific section of the other component's PRD.}

| Component | Dependency | Reference |
|-----------|------------|-----------|
| [{NNN}] {Name} | {What this component needs from it} | `docs/components/{name}/PRD.md` §{section} |

### 3.2 Depended On By

{List other components that depend on this one. This helps the Dev Team agent understand the blast radius of changes.}

| Component | Dependency |
|-----------|------------|
| [{NNN}] {Name} | {What they need from this component} |

## 4. Design System References

{Only include this section for UI-facing components. Delete for backend-only components.}

{Describe which design system specs apply to this component. Reference specific sections — not entire documents.}

| Document | Sections | When to Read |
|----------|----------|--------------|
| `docs/design-guidelines.md` | §{section names} | {When implementing what kind of issue} |
| `docs/figma-export/guidelines/ken-e_design_guidelines.md` | §{section names} | {When implementing what kind of issue} |
| `docs/figma-export/src/imports/{spec}.md` | Entire file | {When implementing what kind of issue} |

## 5. Feature Index

{List every feature-parent issue in Linear for this component. This is the bridge between the PRD and the product roadmap. Update this section whenever a new feature-parent is created.}

| Linear ID | Feature Name | Status | Summary |
|-----------|-------------|--------|---------|
| {TEAM-N} | {Feature parent title} | {Scheduled / In Progress / Done} | {One sentence describing what this feature adds or changes} |

## 6. Global Document References

{List the specific sections of global architecture documents that are relevant to this component. The Dev Team agent reads these sections when the component PRD or an issue references them — not by default.}

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| `docs/{doc-name}.md` | §{section heading} | {When/why a developer working on this component would need to read this} |

## 7. Conventions and Constraints

{List any component-specific conventions that go beyond what CLAUDE.md already covers. Examples: naming patterns, file organization rules, required test patterns, domain-specific validation rules. If there are none, delete this section.}

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Feature Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new directories, new abstractions, new API endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec or design doc section becomes relevant: update §4

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — the agent has limited context. Every sentence should help the agent write better code or avoid mistakes.
-->
