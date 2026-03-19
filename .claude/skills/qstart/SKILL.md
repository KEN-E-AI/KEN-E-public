---
name: qstart
description: |
  Consolidated workflow for starting implementation. Three phases: understand best practices,
  validate plan against codebase patterns, then implement with full test/lint/typecheck verification.
  Replaces the QNEW, QPLAN, and QCODE shortcuts.
user-invocable: true
---

# Start Implementation

This skill runs three phases in sequence to ensure high-quality, consistent code.

## Phase 1: Understand Best Practices

Read and internalize ALL best practices from CLAUDE.md before writing any code:

- **BP-1..BP-3** — Before Coding (clarifying questions, approach confirmation)
- **C-1..C-9** — While Coding (TDD, naming, function design, TypeScript rules)
- **PY-1..PY-7** — Python-Specific (type hints, Pydantic, async, PEP 8, context managers)
- **T-1..T-8** — Testing (colocated tests, integration vs unit, fixtures, assertions)
- **D-1..D-5** — Database (Neo4j sessions, Pydantic models, Firestore batch, indexes)
- **O-1..O-3** — Code Organization (agent/API/frontend separation, shared types)
- **G-1..G-3** — Tooling Gates (lint, format, typecheck)
- **GH-1..GH-3** — Git (Conventional Commits, branch naming)

Your code MUST follow these best practices.

## Phase 2: Validate Plan

Before implementing, analyze similar parts of the codebase and verify your plan:

1. **Consistency** — Does the plan follow the same patterns, naming, and organization as existing code?
2. **Minimal changes** — Does the plan make the smallest set of changes needed? No unnecessary abstractions or over-engineering.
3. **Code reuse** — Does the plan leverage existing utilities, base classes, and shared modules? Reference specific existing implementations as templates.

If issues are found, revise the plan before proceeding.

## Phase 3: Implement and Verify

1. **Implement** the plan following TDD: scaffold stub, write failing test, implement
2. **Run tests** to confirm new tests pass and existing tests aren't broken:
   - Python: `cd api && pytest tests/`
   - Frontend: `cd frontend && npm test`
   - Full suite: `make test`
3. **Run formatting** on newly created/modified files:
   - Frontend: `cd frontend && npm run format.fix`
4. **Run type checking**:
   - Frontend: `cd frontend && npm run typecheck`
   - Python: `make lint` (includes ruff, mypy, codespell)
5. Report results and fix any failures before considering the task complete.
