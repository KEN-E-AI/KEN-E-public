# SK-PRD-00 — Skills Experiment

**Status:** Ready to start (no prerequisites)
**Owner team:** Platform + Security
**Blocked by:** —
**Parallel with:** SK-PRD-01, SK-PRD-03
**Blocks:** SK-PRD-02 (integration decisions depend on findings)
**Estimated effort:** 3–5 days

---

## 1. Context

The User-Authored Skills feature lets users upload a `scripts/` directory as part of a skill bundle. Scripts are executable code (Python / JavaScript) the agent can invoke during task execution. This is the riskiest surface area in the feature because:

1. Scripts are user-authored and will run in a shared Google Cloud runtime.
2. We are planning to use `AgentEngineSandboxCodeExecutor` (ADK's first-party sandbox) for isolation, but the documented threat model is incomplete — network egress, cost per session, cross-skill state contamination, and resource limits are not fully specified.
3. SK-PRD-02's integration design (whether `scripts/` are a real feature or just read-only reference files) hinges on the answers.

This PRD delivers a **spike report** — a written artifact with empirical findings and a go/no-go recommendation — before Sprint 2.6-B commits to wiring the sandbox.

## 2. Scope

### In scope
- Build a throwaway ADK agent with `code_executor=AgentEngineSandboxCodeExecutor(sandbox_resource_name=...)` and a small set of scripts that test each open question.
- Measure: network egress behavior, cost per session, state persistence across invocations, resource limits (CPU/memory/time), file I/O behavior with `scripts/` cited from SKILL.md.
- Test: cross-skill state contamination — one skill's scripts leaves state, a second skill's scripts tries to read it.
- Document: threat model, measured limits, cost model, and a **go / scoped-go / no-go** recommendation for Sprint 2.6-B.
- Deliver: a spike-findings doc committed to `docs/spike-agent-engine-sandbox-findings.md` and summarized in a DESIGN-REVIEW-LOG entry.

### Out of scope
- Implementing any production code or Firestore/GCS changes.
- Building production tracing / metrics — this is exploratory.
- Evaluating alternative sandboxes (Cloud Run jobs, etc.) unless the `AgentEngineSandboxCodeExecutor` is rejected, in which case a short follow-up recommendation is added.

## 3. Dependencies

- **GCP:** Vertex AI project with Agent Engine enabled; service account with `roles/aiplatform.user`.
- **Existing code to study:**
  - `app/adk/agents/` — how an agent is currently constructed (will build a throwaway variant here)
  - `app/adk/tracking/` — existing tracing patterns (reuse if useful, but not required)
- **External:**
  - [ADK Agent Engine Code Execution docs](https://adk.dev/integrations/code-exec-agent-engine/)
  - Vertex AI quota / billing dashboard (for cost measurement)

## 4. Data contract

No persistent data. Spike outputs are:
- `docs/spike-agent-engine-sandbox-findings.md` — markdown report
- `docs/design/DESIGN-REVIEW-LOG.md` — one-line summary entry linking the report

### Report structure (mandatory headings)

```markdown
# Spike — AgentEngineSandboxCodeExecutor

## Summary
[One paragraph: what we learned, recommendation: go / scoped-go / no-go]

## Test harness
[Link to the throwaway branch/commit; a screenshot of a successful run]

## Question 1 — Network egress
### Test
### Result
### Implication for Skills

## Question 2 — Cost per session
### Method
### Result (table: workload → $/session)
### Implication for Skills

## Question 3 — Cross-skill state contamination
### Test
### Result
### Implication for Skills

## Question 4 — Resource limits & failure modes
### Test
### Result
### Implication for Skills

## Question 5 — File I/O with scripts/
### Test
### Result
### Implication for Skills

## Recommendation
[go / scoped-go / no-go, with explicit rationale]

## Follow-ups for Sprint 2.6-B
[Bulleted list of design implications Sprint 2.6-B must honor]
```

## 5. Implementation outline

| Action | Artifact |
|---|---|
| Create | Throwaway branch `spike/agent-engine-sandbox` — do not merge. Delete when spike completes. |
| Create | `scripts/spike/sandbox_test_harness.py` — wires up the throwaway agent |
| Create | Five test scripts in `scripts/spike/skills/` simulating: network call, cross-invocation state, CPU loop, memory balloon, `scripts/` file read |
| Create | `docs/spike-agent-engine-sandbox-findings.md` — the report |
| Modify | `docs/design/DESIGN-REVIEW-LOG.md` — add one-line entry pointing to the report |

Do **not** create production code, Pydantic models, Firestore schemas, or deployment config. The entire output is the report + the deleted branch.

## 6. API contract

N/A.

## 7. Acceptance criteria

1. A spike-findings report exists at `docs/spike-agent-engine-sandbox-findings.md` with all five mandatory question sections filled in with empirical results (not speculation).
2. Each of the five questions below has a concrete, actionable answer:
   - **Network egress:** Can an attacker-controlled script exfiltrate data to an arbitrary external URL? What mitigations exist (VPC-SC, egress policies)?
   - **Cost per session:** What is the approximate $/session for a representative workload (3 tool calls, 1 script invocation running ~10s)?
   - **Cross-skill state contamination:** Does `AgentEngineSandboxCodeExecutor`'s "state persists within a session" apply across scripts from *different* skills, or is state partitioned per-skill?
   - **Resource limits:** What are the CPU, memory, and wall-clock limits? What happens when a script exceeds them? Is the failure contained to the sandbox or does it crash the agent?
   - **File I/O:** When a SKILL.md cites `scripts/extract.py`, can the sandbox-executed code read the file? Does the file come from the sandbox filesystem or is it passed as a string?
3. The report ends with a **go / scoped-go / no-go** recommendation. `scoped-go` explicitly lists which features of Sprint 2.6-B scope must change (e.g., "scripts cannot make outbound HTTP calls — document this as a skill-authoring constraint").
4. A one-line entry is added to `docs/design/DESIGN-REVIEW-LOG.md` linking the report.
5. Any discovered security issues are reported to `security@ken-e.ai` before the report is merged; if severe, the Skills feature is paused until the issue is resolved.

## 8. Test plan

This sprint has no unit/integration tests (no production code ships). The "test plan" is the spike itself — the five questions above are the test matrix.

Each question's test harness must be reproducible: a reviewer should be able to check out the `spike/agent-engine-sandbox` branch, run a single command, and see the same result.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Quota issues prevent running enough sessions to measure cost | Request quota increase day 1; budget for up to 1,000 spike sessions. |
| ADK's `AgentEngineSandboxCodeExecutor` API changes during the spike window | Pin the ADK version at the start of the spike. Note the version in the report. |
| A discovered security issue is severe enough to block the whole feature | Escalate immediately. Do not merge the spike findings publicly until the issue is mitigated or we have a defensible posture. |
| Spike takes longer than 5 days | Hard stop at day 5; report on what's known and file the remaining questions as Sprint 2.6-B blockers. |

### Open questions to carry back to Sprint 2.6-B

- If network egress cannot be restricted, do we tell users "scripts cannot make HTTP calls" in the authoring UI (Sprint 2.6-C) *and* strip network access in the sandbox config, or do we accept the risk and gate on org admin approval?
- If per-session cost is >$0.10 for a representative workload, do we rate-limit sandbox sessions per account?
- If cross-skill state isn't partitioned, does that change our 10-skill-per-agent cap, or do we warn in the UI?

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §3 (Decision #2), §9 (Risks)
- ADK docs: [Agent Engine Code Execution](https://adk.dev/integrations/code-exec-agent-engine/)
- Sister spike: [`docs/spike-adk-reasoning-capture.md`](../../../../spike-adk-reasoning-capture.md), [`docs/spike-otel-pydantic-findings.md`](../../../../spike-otel-pydantic-findings.md) — format / tone reference
- CLAUDE.md rules in scope: none (no production code)
