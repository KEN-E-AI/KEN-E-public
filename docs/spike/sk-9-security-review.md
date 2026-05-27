# SK-9 Security Review — SK-PRD-00 Sandbox Spike (Q1–Q5)

**Date:** 2026-05-25
**Reviewer:** Dev Team (skills-dev-team agent)
**Gate:** SK-PRD-00 §7.AC-5 — security review must be filed before spike report (SK-10) merges publicly
**AC #3 status: accept-with-mitigation — Q3 escalated to High after SK-35 probe (2026-05-27, 50/50 LEAK)**

---

## Summary

This document is the security review required by SK-PRD-00 §7.AC-5 before the
spike report (SK-10) is merged publicly. It covers all five live-capture
findings (Q1, Q3, Q4, Q5; Q2 excluded — see §Q2 below).

The live captures from PR #636 (2026-05-25, post-SK-33 harness rework) produced
a security posture **more restrictive than the pre-spike threat model assumed**:

- Q1 (network egress): default sandbox has no internet egress — 4/4 vectors
  blocked at the network layer. Severity: **Informational** (positive finding).
- Q3 (cross-skill state): same-session state leaks across skills attached to
  one specialist (5/5 vectors LEAK). Severity: **Medium** — explicit opt-in
  only, no cross-account leak, mitigation in scope for SK-PRD-03.
- Q4 (resource limits): ~5-minute sandbox lifetime cap fires as `503
  UNAVAILABLE`. Severity: **Informational** (positive DoS-defence finding).
- Q5 (file I/O): gVisor user-space kernel, empty cwd, no `scripts/` mount, no
  env-var injection. Severity: **Informational** (more restrictive than assumed).

**Net: no escalation to `security@ken-e.ai` is required for a severe/critical
finding. Q3's Medium severity is the only security write-up that warrants
action; its mitigation (SK-PRD-03 authoring-UI warning) is already in the
SK-PRD-03 acceptance criteria.**

---

## Methodology trustworthiness

All live captures used the **direct-mode harness (post SK-33 rework)** — no
`LlmAgent` in the loop, so no hallucination surface. Findings come from Python
standard-library exceptions and stdout observed **inside the sandbox runtime**,
not from LLM-generated output. SK-33 (Done) explicitly delivered: AC-1 (script
executed byte-for-byte), AC-2 (LLM text blocked), AC-3 (proof-of-execution
canary). Trustworthiness is high; every finding is reproducible by running the
corresponding probe against the spike Agent Engine resource
`projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568`
(while it exists; SK-10 deletes it post-merge).

---

## AC #1 — Finding table

| Finding | Source | Security severity | Mitigation | Status |
|---------|--------|-------------------|-----------|--------|
| Q1 — Network egress | `docs/spike/q1-network-egress.md` §Result | **Informational** | Default sandbox already blocks all egress (no action required) | Closed — positive finding |
| Q3 — Cross-skill state (same + cross-session) | `docs/spike/q3-cross-skill-state-fragment.md` §Result; `docs/spike/sk-prd-02-cross-session-tmp-characterisation.md` | **High** (confirmed — SK-35 cross-session LEAK, 50/50 trials 2026-05-27) | `SandboxPool (account_id, config_id)` keying; SK-PRD-03 authoring-UI warning; `SandboxPool._clear_tmp` defence-in-depth (`_CLEAR_TMP_ON_REUSE = True`, SK-35) | In scope — SK-PRD-03 AC owns the warning; SK-35 mitigation active in PR; security packet re-sent (AC-4) |
| Q4 — Resource limits / DoS | `docs/spike/q4-resource-limits.md` §Result | **Informational** | ~5-min sandbox lifetime cap is a built-in DoS defence (no action required) | Closed — positive finding |
| Q5 — File I/O / sandbox surface | `docs/spike/q5-file-io.md` §Result | **Informational** | gVisor isolation + empty cwd is more restrictive than assumed; SK-PRD-03 must change bundle-delivery model (inline content, not filesystem) | SK-PRD-03 delivery-model change in scope |

---

## Q1 — Network egress

**Vector definition.** A user-authored script running inside
`AgentEngineSandboxCodeExecutor` attempts to exfiltrate data or contact a
command-and-control server via DNS, HTTPS, DNS-over-HTTPS (DoH), or raw TCP.

**Reproduction pointer.**
`docs/spike/q1-network-egress.md` §Result — live capture 2026-05-25.
Probe script: `scripts/spike/skills/q1_network_egress.py`.

**Live-capture summary.** 4/4 egress vectors (DNS, HTTPS, DoH, raw-TCP)
returned `blocked` inside the sandbox. DNS resolution fails with
`gaierror: [Errno -3] Temporary failure in name resolution`; raw TCP to
`1.1.1.1:53` fails with `OSError: [Errno 101] Network is unreachable`. The
sandbox container has no DNS resolver and no routing path to the public
internet.

**Severity: Informational.**
The pre-spike research model assumed the sandbox default was unrestricted
egress (preserved in the fragment's §"Original research-based implications"
for traceability). The live probe inverted that assumption. No user-authored
script can exfiltrate data via any of the four tested vectors. This is a
positive security finding — the default posture is already maximally
restrictive without any operator action.

**Mitigation (no action required).** The default is already the desired
state. The `AgentEngineSandboxCodeExecutor` constructor exposes zero
egress-restriction parameters; the restriction comes from the Vertex AI
network layer. If a future operator opens egress via VPC-SC perimeter rules
or PSC-I + Secure Web Proxy, the SK-PRD-03 authoring-UI egress warning
should be added at that time, gated on a config flag.

---

## Q2 — Cost per session (out of scope for this gate)

**Q2 is explicitly excluded from this security review.** Q2's outstanding
work is cost reconciliation — the billing pipeline for 2026-05-27 settlement
is tracked in SK-34 (`docs/spike/q2-cost-per-session-findings.md`). Billing
and cost are not security vectors. No security finding arises from Q2's live
captures; no action is required from this gate.

---

## Q3 — Cross-skill state contamination (same-session)

**Vector definition.** When two or more skills with scripts are attached to
the same specialist agent and executed within the same `Runner` session, a
script from skill B can read filesystem entries, environment variables, Python
module state, and tempdir contents written by a script from skill A. This
allows unintended data sharing between skills authored by the same account.

**Reproduction pointer.**
`docs/spike/q3-cross-skill-state-fragment.md` §Result — live capture
2026-05-25. Probe scripts: `q3_skill_a_writer.py`, `q3_skill_b_reader.py`,
run sequentially in one harness invocation (one `AgentEngineSandboxCodeExecutor`
session, mirroring the SK-PRD-02 `SandboxPool` runtime pattern).

**Live-capture summary.** 5/5 state vectors LEAK same-session (fs, env, mod,
tmpsub, subprocess-pid). The reader script observed every sentinel value
written by the writer script in the same harness session. This is consistent
with `AgentEngineSandboxCodeExecutor`'s documented "state persists within a
session" guarantee — that guarantee applies to the entire session context, not
per-skill.

**Cross-session surface (standalone probe — Vertex container-pool behavior
unresolved).** A supplementary OS-process probe (two separate `uv run python`
invocations sharing a host `/tmp`) confirmed that fs, tmpsub, and
subprocess-pid vectors also leak across process boundaries when `/tmp` is
shared. Whether separate `AgentEngineSandboxCodeExecutor` sessions within
Vertex's container pool reuse the same container's `/tmp` is not confirmed by
the available live captures — session-level container isolation at the Vertex
layer could prevent cross-session `/tmp` sharing. This gap is noted in the
severity rationale below and is tracked in **SK-35** (SK-PRD-02 Wave 2,
blocked by SK-23 + SK-26) which must complete before SK-PRD-02 ships to
production.

**Severity: High** *(escalated from Medium after SK-35 live probe — 2026-05-27, 50/50 trials confirmed cross-session `/tmp` LEAK; see [`docs/spike/sk-prd-02-cross-session-tmp-characterisation.md`](./sk-prd-02-cross-session-tmp-characterisation.md) §Severity classification).*

Rationale:
- **Confirmed scope**: skills within the same specialist agent and the same
  `AgentEngineSandboxCodeExecutor` session. The `SandboxPool (account_id,
  config_id)` key is the designed per-agent isolation boundary.
- **Confirmed cross-session scope (SK-35 2026-05-27 probe):** Vertex reuses the
  container `/tmp` across executor sessions sharing the same
  `sandboxEnvironments/<sid>` resource — 50/50 trials of write → `pool.evict()` →
  `pool.get_or_create()` → read observed the sentinel surviving. fs / tmpsub /
  subprocess-pid vectors therefore also leak **cross-session** within a single
  `(account_id, config_id)` pool bucket. `env` and `mod` remain CLEAN cross-session
  (separate Python processes have separate memory spaces). Cross-account /
  cross-config leakage remains architecturally impossible because the pool keying
  produces a distinct `sandboxEnvironments/<sid>` per `(account_id, config_id)`.
- The sandbox requires `sandbox_code_executor_enabled=true` — an explicit
  admin opt-in per-agent-config (SK-PRD-04 enforces at attach-time). The
  default agent is not affected.
- No cross-account leak was observed or is architecturally possible given
  `SandboxPool` keying by `(account_id, config_id)`.
- The attack surface is limited to cases where a malicious skill is attached
  to the same specialist as a trusted skill, by the same account admin.
  That admin already has write access to both skills, limiting the marginal
  risk.

**Mitigation.**
1. **`SandboxPool (account_id, config_id)` keying (SK-PRD-02 §4.6):** Per-agent
   isolation by design — no cross-config / cross-account leakage. No change required.
2. **`SandboxPool._clear_tmp` defence-in-depth (this PR, SK-35 LEAK branch):**
   `_CLEAR_TMP_ON_REUSE = True` in `app/adk/agents/agent_factory/sandbox_pool.py`;
   every `get_or_create` return path (cache hit and cache miss) issues a Vertex
   `execute_code` call that purges `/tmp` before the executor is returned to the
   caller. Best-effort with 5 s timeout; failures are logged but do not block the
   executor return (the LEAK is mitigated, not eliminated, by intent — pool integrity
   wins under contention). See SK-35 findings doc for residual-risk discussion.
3. **SK-PRD-03 authoring-UI warning:** The skills editor under the `scripts/`
   file uploader must include the following notice:
   > "Scripts attached to the same agent share filesystem, environment, and
   > Python module state within a session. Do not write sensitive data to `/tmp`
   > or rely on state isolation between skills attached to the same agent."
   This warning must be added as an acceptance criterion to SK-PRD-03's
   scripts callout AC — the primary user-facing mitigation depends on it
   being present in that AC list.
4. **10-skill-per-agent cap (SK-PRD-02):** The cap is justified on token-budget
   grounds and serves as a secondary defence — each additional scripts-bearing
   skill increases the shared state surface.

**Escalation status.** Q3's severity is now **High** following the SK-35 probe
escalation. Per SK-9 AC #4 LEAK branch and SK-35 AC-4, the §"Email packet" finding
is re-sent to `security@ken-e.ai` with the corrected severity; defence-in-depth
mitigation (`_clear_tmp`) has shipped alongside the finding so the security team is
informed of both the surface and the response. No emergency feature pause is
required because the mitigation is live in the same PR that documents the
escalation.

---

## Q4 — Resource limits and failure modes (DoS defence)

**Vector definition.** A user-authored script attempts to monopolise the
sandbox indefinitely via a CPU busy-loop or runaway memory allocation, forcing
a denial-of-service condition on other sessions or the overall Vertex AI
endpoint.

**Reproduction pointer.**
`docs/spike/q4-resource-limits.md` §Result — live capture 2026-05-25.
Probe scripts: `q4_cpu_loop.py`, `q4_memory_balloon.py`, `q4_wall_clock.py`.

**Live-capture summary.** CPU-bound and wall-clock-bound probes were killed at
~303–304 s (both returned `503 UNAVAILABLE` from `execute_code` at nearly
identical elapsed times). This is consistent with a single ~5-minute sandbox
lifetime cap per `execute_code` call. Scripts cannot hold a sandbox
indefinitely.

**Severity: Informational** (positive DoS-defence finding).
The ~5-minute cap is a built-in Vertex platform control. No user-authored
script can occupy a sandbox indefinitely. This is the desired security
posture — it bounds any DoS attempt to a finite window. No action is required
from this gate.

**Note on 503 ≠ definitively-a-cap.** `503 UNAVAILABLE` is also returned for
transient Vertex backend errors. The 5-minute interpretation is the most
parsimonious explanation given two independent probes hit it within 1 s of
each other; this interpretation is documented in
`docs/spike/q4-resource-limits.md` §Result and will carry forward to the
consolidated spike findings (SK-10 deliverable).

**Note on memory-balloon DoS (uncharacterised).** The `q4_memory_balloon.py`
probe returned `OUTCOME_OK` with no stdout — the script completed silently or
was killed without an observable error. Memory-only exhaustion as a DoS vector
is not characterised by the available live captures; the ~5-min cap is
confirmed only for CPU-bound and wall-clock-bound workloads. This gap does not
change the Informational severity (no evidence of an exploitable indefinite
hold), but SK-10 must document it as unresolved in the consolidated spike
findings.

**Mitigation (no action required at this gate).** SK-PRD-02 must not retry
`execute_code` on 503 — that response means the sandbox was forcibly
terminated. This is a correctness concern for SK-PRD-02's implementation, not
a security escalation.

---

## Q5 — File I/O with `scripts/` directory (sandbox surface)

**Vector definition.** A user-authored script attempts to read the skill
bundle's filesystem layout from within the sandbox, exfiltrate bundle contents
via env-var injection, or escape the sandbox via the host filesystem.

**Reproduction pointer.**
`docs/spike/q5-file-io.md` §Result — live capture 2026-05-25.
Probe script: `q5_file_io.py` (six access patterns).

**Live-capture summary.** The sandbox runs as `root` inside gVisor
(`Linux-4.19.0-gvisor-x86_64-with-glibc2.36`) with cwd `/home/bard` (empty).
No `scripts/` directory exists at any probed mount point. No SKILL_, BUNDLE_,
KENE_, AGENT_, RESOURCE_, VERTEX_, GOOGLE_, ADK_, or WORKSPACE_-prefixed env
vars are injected. The sandbox surface is more restrictive than the pre-spike
research model assumed.

**Severity: Informational** (positive finding).
The `root` identity inside gVisor is not a security risk — gVisor intercepts
every syscall at the user-space kernel boundary. Container escape via kernel
vulnerabilities is substantially harder than with a stock Linux container. No
user-authored script can read bundle files from the filesystem (the bundle is
not mounted) or exfiltrate skill metadata via env vars (none are injected).

**gVisor kernel version monitoring.** The sandbox runs gVisor with kernel
string `Linux-4.19.0-gvisor`. The gVisor project publishes security advisories
for container-escape vulnerabilities in its user-space kernel. Vertex AI
manages the gVisor runtime and issues platform security bulletins when action
is required. Operators have no independent remediation path — the correct
response to a gVisor advisory is to monitor Vertex AI platform release notes
and apply any mandatory runtime updates Vertex prescribes.

**SK-PRD-03 bundle-delivery model change (correctness, not security).**
Because `scripts/` is not filesystem-mounted inside the sandbox, SK-PRD-03
MUST inline skill bundle content into the script string itself rather than
relying on a `scripts/extract.py` path that does not resolve. This is a
correctness requirement — the authoring UX assumption that a SKILL.md can
cite `scripts/extract.py` for in-sandbox execution does not hold. This
finding requires a design change in SK-PRD-03's bundle-delivery contract;
it is not a security escalation.

**Hygiene item: stray sandbox environment on `ken-e-prod`.** SK-10 documents
one stray `sandboxEnvironment` on production
(`reasoningEngines/5957383247464759296`) that needs cleanup. This is a
resource-hygiene item tracked in SK-10's scope; it does not affect the
security findings of this review and does not block AC #3.

---

## AC #3 disposition

**Q3 escalated to High — AC #3 accept-with-mitigation.**

SK-35 (`docs/spike/sk-prd-02-cross-session-tmp-characterisation.md`) confirmed on
2026-05-27 (50/50 trials) that Vertex reuses container `/tmp` across executor sessions
sharing the same `sandboxEnvironments/<sid>` resource. Q3 severity is revised from
Medium (conditional) to **High**. The SK-PRD-00 §9 risk row "discovered security issue
is severe enough to block the whole feature" now applies and requires an
accept-with-mitigation decision:

* **Mitigation shipped:** `SandboxPool._clear_tmp` defence-in-depth
  (`_CLEAR_TMP_ON_REUSE = True` in `app/adk/agents/agent_factory/sandbox_pool.py`,
  landed in the SK-35 findings PR).
* **Residual risk:** best-effort clearing (5 s timeout, logged on failure); does not
  eliminate the window between executor return and pool re-entry.
* **Sign-off required:** Skills lead + Security lead must acknowledge the residual risk
  before SK-PRD-02 ships to production.
* **PO action:** Re-send the §"Email packet" below to `security@ken-e.ai` with the
  updated Q3 severity (SK-9 AC-4). Post sent timestamp + Message-ID on Linear SK-9.

---

## Email packet (for delivery to security@ken-e.ai)

```
To: security@ken-e.ai
From: ken@ken-e.ai
Subject: [KEN-E Security Review] SK-PRD-00 Sandbox Spike — Q3 escalated to HIGH after SK-35 cross-session probe; mitigation shipped

Hi,

This is the security review for the KEN-E Skills Sandbox Spike (SK-PRD-00).
Per our process, we send security findings to this address before merging
spike documentation publicly.

Summary: no critical or high severity findings. One medium finding (Q3).
Full report: docs/spike/sk-9-security-review.md on main
(also linked from Linear issue SK-9).

This message UPDATES our prior send (2026-05-25 Q1–Q5 packet). The SK-35 live probe
completed on 2026-05-27 and escalates Q3 to HIGH; mitigation has shipped in the same
PR that documents the escalation. No other finding changed.

--- FINDINGS TABLE ---

Finding | Severity | Status
--------|----------|-------
Q1 Network egress | Informational | Positive: sandbox has no internet
                                    egress by default (4/4 vectors blocked)
Q3 Cross-skill state           | High   | ESCALATED 2026-05-27 after SK-35
  (same-session + cross-      |        | live probe (50/50 LEAK). Mitigation
   session confirmed)         |        | shipped: SandboxPool._clear_tmp +
                              |        | SK-PRD-03 authoring-UI warning.
Q4 Resource limits / DoS | Informational | Positive: ~5-min sandbox cap
                                           prevents indefinite occupation
Q5 File I/O / sandbox surface | Informational | Positive: gVisor + empty
                                                 cwd + no env injection
Q2 Cost | Out of scope | Cost reconciliation tracked in SK-34, not a
                          security vector

--- Q1 DETAIL ---

Default Vertex AI sandbox (AgentEngineSandboxCodeExecutor on ken-e-dev,
ADK 1.27.5) blocks all internet egress at the network layer.
DNS: gaierror (-3). HTTPS/DoH: URLError (-3). Raw TCP: Network is unreachable.
No escalation required; this is the desired posture.

--- Q3 DETAIL (HIGH — UPDATED) ---

UPDATE: SK-35 live probe (docs/spike/sk-prd-02-cross-session-tmp-characterisation.md,
2026-05-27, 50/50 trials) confirmed that Vertex reuses the container /tmp between
executor sessions sharing the same sandboxEnvironments/<sid> resource. Q3 severity is
revised to HIGH.

Scripts from two different skills attached to the same specialist agent share
filesystem, environment, and Python module state within a session (5/5 state vectors
LEAK same-session). Additionally, fs, tmpsub, and subprocess-pid vectors LEAK
cross-session — surviving SandboxPool.evict() + new SandboxPool.get_or_create() cycles
for the same (account_id, config_id) pool key. The probe ran against the live
SK-PRD-02 SandboxPool path (not a raw AgentEngineSandboxCodeExecutor) so the finding
characterises production pool-reuse semantics, not raw executor semantics.

Isolation boundary: SandboxPool (account_id, config_id) keying prevents cross-account
or cross-specialist leakage by construction (different keys produce different
sandboxEnvironments/<sid> resources). No cross-account or cross-specialist surface
was observed or is architecturally possible.

Mitigation (shipped in the SK-35 findings PR):
- SandboxPool._clear_tmp defence-in-depth purges /tmp on every get_or_create return
  path (cache hit and cache miss); _CLEAR_TMP_ON_REUSE = True.
- Best-effort 5-second timeout; failures are logged but the executor is still
  returned (pool integrity wins under contention).
- SK-PRD-03 authoring-UI warning remains required as the user-facing mitigation.

Residual risk: the clearing step is post-hoc — a sentinel written by session A is
purged before session B is returned to a caller, but the window between Vertex
container reuse and the clear is non-zero. A future Vertex platform change that
clears /tmp natively between sessions would close that window entirely; until then,
defence-in-depth + the SK-PRD-03 warning are the load-bearing mitigations.

--- METHODOLOGY ---

Q1, Q3 (same-session), Q4, Q5 findings from the direct-mode harness (no LlmAgent, no
hallucination surface), run 2026-05-25 from a credentialled workstation against spike
Agent Engine projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568.
SK-33 (Done) validated the harness trustworthiness.

Q3 cross-session finding from the SK-35 probe (scripts/skills/sandbox_cross_session_tmp_probe.py),
run 2026-05-27 from the same credentialled workstation against the same Agent Engine
(sandbox 8580220406768599040). 50 trials, write → SandboxPool.evict() → SandboxPool.get_or_create() → read.
50/50 LEAK. See docs/spike/sk-prd-02-cross-session-tmp-characterisation.md for the
full trial table and methodology.

Please acknowledge receipt of this updated finding. If you assess that the shipped
mitigation is insufficient, reply with your assessment and we will pause SK-PRD-02
ship-readiness until the next steps are agreed.

Thanks,
KEN-E Skills team
```

> **AC #2 action for PO:** After sending the email above from `ken@ken-e.ai`,
> post a comment on Linear issue SK-9 with the sent timestamp and Message-ID:
> "Email sent to security@ken-e.ai at [ISO-8601 timestamp]. Message-ID:
> [message-id]." That comment, combined with this document, completes AC #2.

---

*This document satisfies SK-PRD-00 §7.AC-5 (security review pre-merge gate)
and SK-9 AC #1 (write-up listing every non-trivial finding with severity).
Merge of SK-10 is conditional on AC #2 (email sent, timestamp + Message-ID
recorded on SK-9). AC #3 disposition: accept-with-mitigation — Q3 escalated to High after SK-35 (2026-05-27); mitigation shipped via `SandboxPool._clear_tmp`.*
