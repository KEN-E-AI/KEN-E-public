# REVIEW.md

Code Review rules. Treat violations as findings.

## Always Check

- **Integration tests** for new API endpoints (`api/tests/`)
- **Pydantic validation** for all external inputs (request bodies, query params)
- **Type hints** on all Python function arguments and return values (PY-1)
- **`import type`** for TypeScript type-only imports (C-6)
- **Branded types** for entity IDs in TypeScript (C-5)
- **No bare excepts** — handle exceptions explicitly (PY-7)
- **No hardcoded credentials** — use environment variables or Secret Manager (D-5)
- **Conventional Commit format** on PR title (GH-1)
- **Context managers** for Neo4j sessions and file operations (D-1, PY-5)
- **TDD evidence** — new code should have corresponding tests (C-1)

## Style

- Small functions over classes (C-3, C-4)
- f-strings in Python (PY-6)
- `cn()` for conditional Tailwind classes in frontend
- `type` over `interface` in TypeScript unless merging is needed (C-8)
- Async/await for I/O in FastAPI endpoints (PY-3)
- No comments except critical caveats (C-7)

## Skip

- Generated files under `frontend/src/components/ui/`
- Lock files (`package-lock.json`, `uv.lock`)
- Formatting-only changes (whitespace, import order)
- Notebook outputs
- Files in `data_ingestion/` pipeline configs
