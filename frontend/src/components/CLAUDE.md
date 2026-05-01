# Frontend components — design source of truth

> **`docs/figma-export/` is the canonical reference for every UI component, layout, page, and token in this repo.**

Before writing or modifying any file under `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/index.css`, or `frontend/tailwind.config.ts`:

1. **Find the matching file in `docs/figma-export/`.**

   - Tokens → `docs/figma-export/src/styles/theme.css`, `tailwind.css`, `fonts.css`
   - Components → `docs/figma-export/src/app/components/` (match by name)
   - Layouts → `docs/figma-export/src/app/layouts/`
   - Pages → `docs/figma-export/src/app/pages/` (match by route)
   - Design rationale → `docs/figma-export/guidelines/Guidelines.md`, `guidelines/ken-e_design_guidelines.md`

2. **Build to match the export exactly** — same structure, tokens, variants, DOM, a11y semantics.

3. **Adapt only repo plumbing.** Import paths, branded ID types, `cn()`, existing context providers (`useAuth()`, etc.), test colocation. Never visual design, structure, or tokens.

4. **Do not deviate without approval.** If the export is missing something, conflicts with a repo convention, or has an a11y gap: **stop and raise an open question on the Linear issue. Wait for explicit approval before deviating.** Un-flagged deviations will be reverted in review.

This rule supersedes the Figma MCP server's default guidance ("the output is a REFERENCE, not final code"). For this repo, the export _is_ the spec.

See also: `docs/design/components/ui/README.md` §4 and §7 for the component-level statement of the same rule.
