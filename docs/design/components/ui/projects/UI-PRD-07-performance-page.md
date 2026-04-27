# UI-PRD-07 — Performance Page (RETIRED)

**Status:** **RETIRED — Subsumed by [PE-PRD-01](../../performance/projects/PE-PRD-01-page-shell-and-routing.md)**
**Owner team:** —
**Blocked by:** —
**Parallel with:** —
**Estimated effort:** —

---

> **This PRD is retired and is preserved as a historical reference only.** It is not on the implementation backlog. Its scope is delivered by the **[Performance component](../../performance/README.md)** (`PE-PRD-01` … `PE-PRD-08`), which redesigns `/performance` as a five-tab surface (Analysis / Simulations / Targets / Diagnostics / Configuration) backed by SAR-E. The legacy `frontend/src/pages/Performance.tsx` is deleted by `PE-PRD-01`, not by this PRD.
>
> The §11 Cleanup table below — covering `Recommendations.tsx`, `Campaigns.tsx`, `Reports.tsx`, `Index.tsx`, `Simulations.tsx` — is **not executed by UI-PRD-07**. Each row is owned by the PRD that ships the replacement surface (PE-PRD-02 / PE-PRD-03 / PR-PRD-08 / DB-PRD-01 / PE-PRD-01 respectively). The table is preserved here as a checklist so the subsumption decision history remains traceable.
>
> **References for the subsumption decision:**
> - [`docs/design/DESIGN-REVIEW-LOG.md`](../../../../DESIGN-REVIEW-LOG.md) — UI-PRD-07 marked subsumed
> - [`docs/KEN-E-System-Architecture.md`](../../../../KEN-E-System-Architecture.md) §7.1, §12 — UI-PRD-07 folded into PE-PRD-01
> - [`docs/design/components/PROJECT-PLANNER.md`](../../PROJECT-PLANNER.md) — release column = "— (subsumed by PE-PRD-01)"
> - [`docs/design/components/performance/README.md`](../../performance/README.md) §3.1 — Performance page replaces legacy `Performance.tsx` entirely

---

## Historical scope (for reference only — DO NOT IMPLEMENT)

The original scope of this PRD was a presentation-layer redesign of the legacy `frontend/src/pages/Performance.tsx` onto `LayoutC`, with new metric tiles, themed charts, and a filter bar — preserving existing analytics data loading. That approach was superseded once the Performance component was carved out with its own analytical backend (SAR-E, statistical forecasting, IRF scenarios, LLM-driven target derivation), making a presentation-only redesign meaningless.

The original §11 Cleanup table identified five legacy pages to drop. Each row's deletion lands with the PRD that ships its replacement surface — none of these are UI-PRD-07's responsibility:

| File | Route(s) | Replacement surface (and deleting PRD) |
|------|----------|---------------------------------------|
| `frontend/src/pages/Recommendations.tsx` | `/recommendations` | Performance **Analysis tab** — PE-PRD-02 |
| `frontend/src/pages/Campaigns.tsx` | `/campaigns` | Calendar + **Campaign Management** — PR-PRD-08 |
| `frontend/src/pages/Reports.tsx` | `/reports` | **Dashboards** — DB-PRD-01 |
| `frontend/src/pages/Index.tsx` | `/measurement-plan` | Dropped — no replacement; deletion folds into PE-PRD-01's `App.tsx` route cleanup |
| `frontend/src/pages/Simulations.tsx` | `/simulations` | Performance **Simulations tab** — PE-PRD-03 |
