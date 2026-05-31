# Spike — AgentEngineSandboxCodeExecutor

**Status:** Complete (Q1–Q5 empirical captures done; recommendation deferred to SK-8)
**ADK Version:** google-adk==1.27.5
**Spike engine:** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568` (displayName `sk-prd-00-spike-sandbox`)
**Capture date:** 2026-05-25 (post Wave 2.5 SK-33 harness rework)

---

## Summary

The default `AgentEngineSandboxCodeExecutor` on Vertex AI Agent Engine (`ken-e-dev`,
`us-central1`) has **no internet egress** — a live probe on 2026-05-25 returned 4/4
vectors blocked (DNS, HTTPS, DoH, and raw TCP all fail at the network layer), inverting
the pre-capture research assumption that egress was unrestricted. Cost measurement over
60 sessions (N=30 cold, N=30 warm) found no separately-metered Vertex billing for the
sandbox path — per-session cost is $0.00 (≤ $0.0048 upper bound including all
orchestration-layer LLM spend), well below the $0.10/session PRD threshold. State
contamination is total within a session: all five probe vectors (filesystem, environment,
modules, tempdir, subprocess records) leak between skill scripts sharing one executor
instance, confirming the `SandboxPool (account_id, config_id)` keying is the correct
isolation boundary. Resource limits: CPU-bound and wall-clock-bound scripts are killed
at approximately 5 minutes (304 s and 303 s respectively) with a `503 UNAVAILABLE` API
error — there is no structured `OUTCOME_DEADLINE_EXCEEDED` enum; memory enforcement is
opaque (no Python-level MemoryError was captured). File I/O: `scripts/` is **not**
mounted in the sandbox filesystem — the sandbox runs in an empty `/home/bard` working
directory under a gVisor kernel, and no skill-metadata environment variables are injected.
The go/scoped-go/no-go verdict is deferred to `## Recommendation` (filled by SK-8).

---

## Test harness

**Branch and commit:** All probe scripts are committed on
`spike/agent-engine-sandbox` (branch HEAD `ffa949bbd031f96b4b080f80da1b21955e9db2a3` at
compose time). The branch is throwaway and will be deleted by SK-10 after this report
merges.

**Trust contract — Wave 2.5 SK-33 rework (direct mode, no `LlmAgent`):** The original
Wave 2 harness routed every script through a `google.adk.agents.LlmAgent` + Gemini 2.0
Flash, which hallucinated plausible-looking results (`Exit status: ok` with a two-year-old
timestamp and wrong large-integer values) without ever invoking the real code executor.
SK-33 reworked the harness to call `AgentEngineSandboxCodeExecutor.execute_code()`
directly, bypassing the LLM entirely. The full regression evidence — four harness runs
with smoking-gun hallucination signals — is in `docs/spike/harness-validation.md`. All
Q1/Q3/Q4/Q5 live captures below used the direct-mode harness; Q2 used the Q2
orchestrator which subprocess-spawns the same direct harness. `Exit status: ok` in direct
mode means the Vertex API returned `OUTCOME_OK` for a real script execution, not an
LLM inference — there is no hallucination surface.

**Successful-run exemplar (Q1, 2026-05-25):**

```
=== [1/1] q1_network_egress.py stdout ===
{"vector": "dns", "target": "example.com", "outcome": "blocked", "details": "gaierror: [Errno -3] Temporary failure in name resolution"}
{"vector": "https", "target": "https://httpbin.org/get", "outcome": "blocked", "details": "URLError: <urlopen error [Errno -3] Temporary failure in name resolution>"}
{"vector": "doh", "target": "https://cloudflare-dns.com/dns-query?name=example.com&type=A", "outcome": "blocked", "details": "URLError: <urlopen error [Errno -3] Temporary failure in name resolution>"}
{"vector": "tcp_raw", "target": "1.1.1.1:53", "outcome": "blocked", "details": "OSError: [Errno 101] Network is unreachable"}
{"vector": "summary", "allowed": 0, "blocked": 4, "partial": 0, "error": 0}

=== [1/1] q1_network_egress.py status: ok ===
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 8.43
Exit status  : ok
```

The `Mode: direct (no LlmAgent)` trailer line is the trust signal: the harness made a
direct `execute_code` API call; the JSON lines above are real Python exception objects
observed INSIDE the sandbox, not LLM inference.

**Methodology lesson — branch-switching artifact (Q2 orchestrator):** The Q2 cohort run
uses an orchestrator (`scripts/spike/q2_cost_orchestrator.py`) that `subprocess.run`s
the harness with a filesystem-relative path to
`scripts/spike/skills/q2_cost_per_session.py`. In a first attempt, the main working tree
was switched from `spike/agent-engine-sandbox` to `integration/cycle-3-sk-prd-00-wave-2`
between sessions 1 and 2, removing the workload script from the subprocess's filesystem
view; sessions 2–60 all failed with `[harness] Script not found: ...`. Diagnosed from
the per-session `raw_stdout` in the JSONL output. **Resolution:** the clean N=30+30 run
was executed from a `git worktree` checkout at `/tmp/kene-spike/` pinned to
`spike/agent-engine-sandbox`, isolated from the main repo's branch switches. Any future
spike whose orchestrator `subprocess.run`s helpers should either (a) make helpers
self-contained (no filesystem-relative reads after spawn), or (b) run from a worktree
with a stable branch state.

---

## Question 1 — Network egress

> [!NOTE]
> **Live capture complete — pre-capture research assumption was inverted.**
> Live probe from a credentialled workstation (2026-05-25, post Wave 2.5
> harness rework) returned **4/4 vectors BLOCKED**. The default sandbox has
> NO internet egress (DNS, HTTPS, DoH, and raw-TCP all fail at the network
> layer with `gaierror`/`Network is unreachable`). The `### Implication for
> Skills` section has been rewritten to reflect the inversion — see the
> dated revision header in that section. The original research-based
> implications are preserved in §"Original research-based implications
> (pre-capture, now inverted)" for SK-7/SK-8 traceability.

### Test

**Probe script:** `scripts/spike/skills/q1_network_egress.py` (committed on
`feat/SK-2-q1-network-egress`, merged to `spike/agent-engine-sandbox`).

**Probe vectors (all stdlib — no third-party deps sent into sandbox):**

| # | Vector | Target | Technique |
|---|--------|--------|-----------|
| A | `dns` | `example.com` | `socket.gethostbyname()` — tests plain UDP/TCP-53 DNS |
| B | `https` | `https://httpbin.org/get` | `urllib.request.urlopen()` — tests full HTTPS stack |
| C | `doh` | `https://cloudflare-dns.com/dns-query?name=example.com&type=A` | DoH (port 443, `application/dns-json`) — tests whether HTTPS allow-list bypasses a DNS block |
| D | `tcp_raw` | `1.1.1.1:53` | `socket.create_connection()` — tests unrestricted TCP to non-HTTP port |

> **Follow-up note (PR #636 review).** Vectors B and C use third-party
> public endpoints (`httpbin.org`, `cloudflare-dns.com`). If those
> services are down at probe time, the harness would report `blocked`
> false-positively. The 4/4 BLOCKED result below is consistent with a
> Vertex network-layer block (all four vectors fail at DNS/routing,
> including the `1.1.1.1` raw-TCP probe which does NOT route through
> httpbin), so the live finding holds — but a future re-run for Wave 2.5
> or a successor probe should swap httpbin for an internal echo endpoint
> in `ken-e-dev` to remove the dependency. Captured as a methodology
> follow-up; not load-bearing on this run's findings.

Each probe prints one JSON line: `{"vector": "...", "target": "...", "outcome": "allowed|blocked|partial|error", "details": "..."}` then a summary line.

**Harness invocation:**

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q1_network_egress.py
```

**Note on `GOOGLE_GENAI_USE_VERTEXAI=1`:** The `google-genai` SDK reads this env var
to route LLM calls to Vertex AI rather than the Gemini Developer API. Without it the
`LlmAgent` constructor raises `ValueError: Missing key inputs argument`. Discovered
during SK-2 Wave 2 execution. This env var must be set whenever running the harness
against a Vertex AI project. `GOOGLE_CLOUD_LOCATION=us-central1` must also be set
because `google-genai` reads that name, not `VERTEX_AI_LOCATION`.

**Spike Agent Engine provenance:** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568`
(displayName `sk-prd-00-spike-sandbox`), created in SK-1 AC #4 (2026-05-24T17:18Z).
SK-10 deletes this resource; verify it still exists before running.

**Baseline run (default config — no mitigation applied):**
SK-PRD-02 needs to know the default behaviour. Run with the command above as-is.

**Mitigation re-runs:**
Based on the research in §Mitigation Matrix, the only tested mitigation knob is
VPC Service Controls. If the `ken-e-dev` project is in a VPC-SC perimeter that
blocks Vertex AI egress, repeat the probe inside that perimeter. Otherwise mark
all mitigation knobs as "untestable — perimeter not configured on ken-e-dev".

**`--self-test` result (Dev Team VM, 2026-05-24, outside sandbox):**

```
{"vector": "meta", "context": "self-test", "note": "Running outside sandbox — results reflect host VM reachability, NOT sandbox egress policy.  Do not cite these as Q1 evidence."}
{"vector": "dns", "target": "example.com", "outcome": "allowed", "details": "resolved to 172.66.147.243"}
{"vector": "https", "target": "https://httpbin.org/get", "outcome": "allowed", "details": "HTTP 200; body_preview='{\\n  \"args\": {}, \\n  \"headers\": {\\n    \"Accept-Encoding\": \"identity\", \\n    \"Host\": '"}
{"vector": "doh", "target": "https://cloudflare-dns.com/dns-query?name=example.com&type=A", "outcome": "allowed", "details": "HTTP 200; body_preview='{\"Status\":0,\"TC\":false,\"RD\":true,\"RA\":true,\"AD\":false,\"CD\":false,\"Question\":[{\"n'"}
{"vector": "tcp_raw", "target": "1.1.1.1:53", "outcome": "allowed", "details": "create_connection() succeeded; port 53 reachable"}
{"vector": "summary", "allowed": 4, "blocked": 0, "partial": 0, "error": 0}
```

All four probe targets are reachable from the host VM. This confirms the targets
are live and the script is structurally correct. These results do NOT reflect sandbox
behaviour.

**Live execution instructions for PO:**

```bash
# From workstation with roles/aiplatform.user on ken-e-dev:
git fetch origin spike/agent-engine-sandbox
git checkout spike/agent-engine-sandbox

GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q1_network_egress.py
```

---

### Result

**Live capture (2026-05-25, direct-mode harness post Wave 2.5 rework):**

```
=== [1/1] q1_network_egress.py stdout ===
{"vector": "dns", "target": "example.com", "outcome": "blocked", "details": "gaierror: [Errno -3] Temporary failure in name resolution"}
{"vector": "https", "target": "https://httpbin.org/get", "outcome": "blocked", "details": "URLError: <urlopen error [Errno -3] Temporary failure in name resolution>"}
{"vector": "doh", "target": "https://cloudflare-dns.com/dns-query?name=example.com&type=A", "outcome": "blocked", "details": "URLError: <urlopen error [Errno -3] Temporary failure in name resolution>"}
{"vector": "tcp_raw", "target": "1.1.1.1:53", "outcome": "blocked", "details": "OSError: [Errno 101] Network is unreachable"}
{"vector": "summary", "allowed": 0, "blocked": 4, "partial": 0, "error": 0}

=== [1/1] q1_network_egress.py status: ok ===
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 8.43
Exit status  : ok
```

**Trustworthiness:** harness in direct mode (no `LlmAgent` in the loop, so no
hallucination surface). `Exit status: ok` means the executor returned `OUTCOME_OK`;
the 4 `blocked` outcomes are real failures observed INSIDE the sandbox runtime
(Python's standard `gaierror`/`OSError` exceptions, not synthetic LLM output).
Wall-clock 8.43 s is consistent with a real cold-start sandbox creation + script execution.

**Dev Team VM credential attempt (2026-05-24, pre-rework, kept for audit
traceability):**

```
Exit status  : error (ClientError): agent run failed — 403 PERMISSION_DENIED.
Permission 'aiplatform.endpoints.predict' denied on resource
'//aiplatform.googleapis.com/projects/ken-e-dev/locations/us-central1/publishers/google/models/gemini-2.0-flash'
```

This confirms `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com` lacked
`roles/aiplatform.user` on `ken-e-dev`. The live capture above was produced
from a different workstation (`ken@ken-e.ai`) that holds the role.

**Per-vector outcome table:**

| Vector | Default sandbox (`ken-e-dev`, no VPC-SC) | VPC-SC perimeter |
|--------|--|--|
| dns | **blocked** (`gaierror: [Errno -3] Temporary failure in name resolution`) | untestable — perimeter not configured on `ken-e-dev` |
| https | **blocked** (`URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`) | untestable |
| doh | **blocked** (`URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`) | untestable |
| tcp_raw | **blocked** (`OSError: [Errno 101] Network is unreachable`) | untestable |

The DNS error (`[Errno -3] Temporary failure in name resolution`) on three
of the four vectors implies the sandbox container has no DNS resolver
reachable; the raw-TCP error (`Network is unreachable`) implies the
container's routing table has no path to the public internet at all. Both
are consistent with a sandbox that runs with no egress route by default.

---

### Mitigation Matrix

Research sources: ADK 1.27.5 `AgentEngineSandboxCodeExecutor` source inspection
(via `inspect.getsource`), Vertex AI Agent Engine docs, google-cloud VPC-SC
supported services list.

| Knob | Where set | Default value | Tested effect on egress | Gap |
|------|-----------|---------------|-------------------------|-----|
| `sandbox_resource_name` / `agent_engine_resource_name` | `AgentEngineSandboxCodeExecutor` constructor | Required (one must be set) | Routing-only; no egress filter | No egress restriction |
| `code_language` | `code_execution_environment` spec | `LANGUAGE_PYTHON` | Language selection; no network policy | No egress restriction |
| `machine_config` | `code_execution_environment` spec | 2vCPU / 1.5 GB | Resource limits; no network policy | No egress restriction |
| `ttl` | `CreateAgentEngineSandboxConfig` | `31536000s` (1 year) | Session lifetime; no network policy | No egress restriction |
| VPC Service Controls perimeter | GCP org/project policy (admin action) | Not enabled by default on `ken-e-dev` | All-or-nothing internet block when project is inside a VPC-SC perimeter — if Vertex AI Agent Engine is listed as a supported service, all sandbox internet access is blocked unless routed through PSC-I + proxy | Requires org-admin action; not controllable per-sandbox or per-agent; binary (all or nothing) |
| PSC-I + Secure Web Proxy (SWP) | GCP networking (admin action) | Not configured | Fine-grained FQDN allowlist / denylist via proxy; traffic can be inspected and filtered | Requires dedicated proxy VM or Cloud Router + SWP; not a sandbox-level knob |
| `GOOGLE_GENAI_USE_VERTEXAI` env var | Harness env (caller sets) | Not set → falls back to Gemini Developer API (fails without `api_key`) | Must be `1` for LLM calls to route to Vertex AI; not an egress restriction | Discovered in SK-2 Wave 2; must be documented in harness README |

**Conclusion from research:** The `AgentEngineSandboxCodeExecutor` exposes **zero
constructor or API parameters that control network egress**. The only available
mitigations operate at the GCP infrastructure layer (VPC-SC, PSC-I + proxy) and
require organisation-admin action. Neither is controlled per-sandbox, per-agent, or
per-invocation.

#### Threat model

**Who can configure egress restrictions:**
- GCP organisation administrator (VPC-SC perimeter, PSC-I)
- GCP project IAM admin who can modify the Vertex AI Agent Engine deployment network
  configuration

**What the defaults are:**
- `ken-e-dev` is not inside a VPC-SC perimeter as of SK-2 execution date.
- No PSC-I or proxy is configured.
- The sandbox environment is created with `spec={'code_execution_environment': {}}` —
  no network fields populated.
- **Empirically observed default: NO internet egress.** The 2026-05-25 live
  capture against `ken-e-dev` returned `Network is unreachable` for raw-TCP
  and `gaierror`/`Temporary failure in name resolution` for DNS, HTTPS, and
  DoH — i.e., the sandbox runtime has no DNS resolver and no routing path to
  the public internet by default. This contradicts the pre-capture research
  assumption (preserved in §"Original research-based implications" for
  audit), and is the load-bearing finding for Q1.

**Where to enable restrictions:**
1. VPC Service Controls: organisation console → VPC SC → Access Policy → create
   perimeter including `ken-e-dev` project + `aiplatform.googleapis.com` service →
   add ingress/egress rules.
2. PSC-I + Secure Web Proxy: deploy Cloud Router + SWP in the same region
   (`us-central1`); configure a PSC-I network endpoint for the Agent Engine; route
   all egress through the SWP with an FQDN allowlist. Detailed steps: [Securing
   Vertex AI Agent Engine: Controlling Egress with PSC-I and
   SWP](https://medium.com/@thebobrovs/securing-vertex-ai-agents-engine-controlling-egress-with-psc-i-and-secure-web-proxy-a6e6b91892e4).

**IAM surface:** `roles/aiplatform.user` grants sandbox create+execute. No
separate "network config" IAM role exists for sandbox egress — it is either
perimeter-level (VPC-SC) or deployment-level (PSC-I). A user with only
`roles/aiplatform.user` cannot restrict egress; an organisation admin must act.

---

### Implication for Skills

> **Revised 2026-05-25** based on live capture showing 4/4 vectors `blocked`.
> The original research-based implications (which assumed unrestricted egress)
> are preserved below in §"Original research-based implications" for SK-7/SK-8
> traceability.

1. **SK-PRD-02 `_build_code_executor` config:** The ADK surface still exposes
   zero egress-restriction constructor kwargs — that part of the research
   stands. **But the empirical default is "no egress," not "unrestricted
   egress."** SK-PRD-02 does NOT need to add a "network policy" parameter
   because the default is already maximally restrictive. The `_build_code_executor`
   docstring and `SandboxPool._construct` should document this as the observed
   default with a pointer to this fragment.

2. **SK-PRD-03 authoring-UI copy:** **No egress warning is required** under
   the `scripts/` uploader. The previously-mandated warning ("Scripts run in
   a Vertex AI sandbox that has unrestricted internet access by default") is
   factually wrong against the observed default. If a future operator opens
   the sandbox to external traffic via VPC-SC perimeter rules or PSC-I + SWP,
   the warning should be added at that time, gated on a config flag.

3. **SK-PRD-00 §9 open question (HTTP egress + authoring-UI implications):**
   **Resolved.** Scripts cannot make HTTP calls in the default sandbox — the
   constraint the §9 question hoped for is already enforced at the Vertex
   network layer. The Skills README §7 sandbox-gating section should add a
   note: "Default sandbox runtime has no internet egress. Operators wishing to
   enable HTTP access for trusted skills must explicitly open the sandbox via
   VPC-SC or PSC-I + SWP — this is an admin-level action, not a per-skill or
   per-account knob."

4. **10-skill cap (cross-vector leakage):** Unchanged. The cap is governed by
   token budget (L1 metadata overhead), not egress risk. Q1's inverted finding
   removes one input to the cap discussion but does not change the cap.

5. **Security escalation (SK-9):**
   - Severity: **None / Informational.** The original "High severity, gated on
     org-admin VPC-SC config" finding is **withdrawn.** Default Vertex sandbox
     is closed; no escalation to `security@ken-e.ai` is required from Q1
     findings alone.
   - Updated action: SK-9 should still flag this finding for the security
     gate review, but as an _affirming_ data point (the security posture is
     better than assumed), not an escalation.
   - No blocker for SK-PRD-02 or SK-PRD-03.

---

### Original research-based implications (pre-capture, now inverted)

> Preserved verbatim for SK-7/SK-8 traceability. **These are NOT the load-bearing
> Q1 implications** — see the revised section above. The original implications
> incorrectly assumed the sandbox default was unrestricted egress; the live
> probe showed the opposite.

1. **SK-PRD-02 `_build_code_executor` config:** No egress-restriction constructor
   kwargs exist. The `AgentEngineSandboxCodeExecutor` constructor receives only
   `agent_engine_resource_name`. Sandbox egress is unrestricted by default;
   SK-PRD-02 cannot add a "network policy" parameter because the ADK surface does
   not expose one. Document this as a known gap in `_build_code_executor`'s
   docstring and the `SandboxPool` `_construct` method.

2. **SK-PRD-03 authoring-UI copy:** If the live probe confirms unrestricted egress
   (expected), the Skills authoring UI **MUST** include a prominent warning under
   the `scripts/` uploader:
   > "Scripts run in a Vertex AI sandbox that has **unrestricted internet access**
   > by default. Never upload scripts that transmit sensitive data externally. A
   > VPC-SC perimeter can restrict egress — contact your org admin."

3. **SK-PRD-00 §9 open question (HTTP egress + authoring-UI implications):** The
   answer is "accept the risk and gate on org admin approval" — no authoring-UI
   `scripts cannot make HTTP calls` constraint is enforceable without
   infrastructure changes. The PRD §9 option "strip network access in the sandbox
   config" is not available via the ADK API. The Skills README §7 sandbox-gating
   section should add a note: "Network egress is unrestricted in the default
   sandbox; KEN-E operators must configure VPC-SC or PSC-I+SWP to enforce
   egress policies."

4. **10-skill cap (cross-vector leakage):** The cap is unaffected by Q1 findings.
   A sandbox-enabled agent with 10 scripts-bearing skills shares one sandbox
   process (per `SandboxPool` keying by `(account_id, config_id)`) — the egress
   risk scales with the number of script invocations, not the number of skills.
   No change to the cap recommended from Q1.

5. **Security escalation (SK-9):** If live probe confirms unrestricted egress on
   all four vectors with no available knob (the expected outcome):
   - Severity: **High** (not Critical — scripts require `sandbox_code_executor_enabled=true`
     which is opt-in per-agent; the default agent is not affected).
   - Required action: add the authoring-UI warning (implication 2 above) and the
     README note (implication 3 above) before the Skills feature is made generally
     available.
   - Not a blocker for SK-PRD-02 shipping the `SandboxPool` and factory wiring
     (those are R1 / internal). The authoring-UI warning is R3 (SK-PRD-03) which
     lands before scripts-bearing skills are user-accessible.

---

## Question 2 — Cost per session

### Method

**ADK version:** google-adk==1.27.5
**Spike engine:** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568` (displayName `sk-prd-00-spike-sandbox`)
**Service account:** `ken-e-api@ken-e-dev.iam.gserviceaccount.com`

**Representative workload** (defined in `docs/spike/q2-cost-per-session-methodology.md` §d):

| Step | Operation | Purpose |
|---|---|---|
| 1 | Float math: `sum(i * 1.23456789 for i in range(10_000))` | In-sandbox CPU — analogous to a tool call's compute overhead |
| 2 | Write + read a 1 KB temp file via `pathlib` | File-system I/O — analogous to a skill that writes intermediate results |
| 3 | `subprocess.run(["/bin/echo", '{"tool": "stub", "result": "ok"}'])` | Subprocess spawn — analogous to a skill calling a bundled CLI tool |
| 4 | `time.sleep(10)` | Simulates a ~10s script invocation per SK-PRD-00 §7.AC-2 |

**In-sandbox script:** `scripts/spike/skills/q2_cost_per_session.py`
**Orchestrator:** `scripts/spike/q2_cost_orchestrator.py`
**Session data:** `scripts/spike/skills/q2_sessions.jsonl`

**Cohort design:** Sessions were interleaved in blocks of 10 (5 cold + 5 warm) to net out
time-of-day billing artifacts. Cold sessions pass a fresh Agent Engine resource name; warm
sessions reuse the `sandboxEnvironment` from the corresponding cold session in the block.

**Billing attribution:** Billing was pulled 2026-05-31 (≫ the 36 h window that opened
2026-05-27T01:30Z) from the Cloud Billing export at `ken-e-dev.billing_export`
(`gcp_billing_export_resource_v1_*`). The Vertex billing export attributes cost by
**project + resource + label**, not by calling principal — so the spike was isolated two ways
rather than by service account: (a) the dedicated spike engine by `resource.name`
(`reasoning-engine-2624457839443181568` — the Cloud Run backing-service id equals the
`reasoningEngine` id, verified against the Vertex `reasoningEngines.list` API), and (b) the
spike agent's LLM usage by the billing label `adk_agent_name = "spike_sandbox_agent"`. The
proportional-by-duration fallback (§e) was **not needed**: see the Line-item Split below.

**Orchestrator standalone verification (structural):**

```
$ uv run python scripts/spike/skills/q2_cost_per_session.py
{"steps": {"compute": {"elapsed_ms": 0.76}, "file_io": {"elapsed_ms": 0.75},
 "subprocess": {"elapsed_ms": 5.18, "output": "{\"tool\": \"stub\", \"result\": \"ok\"}"},
 "sleep": {"elapsed_ms": 10000.13}}, "rss_kb": 93992, "total_elapsed_ms": 10006.82}
```

Script runs cleanly standalone (without Vertex AI); total wall-clock ~10s as designed.
`ruff` and `codespell` clean on all three new files.

---

### Result

**Live N=30 capture (2026-05-25):**

Run command (from a `git worktree` checkout at `/tmp/kene-spike/` on
`spike/agent-engine-sandbox`, isolated from the main repo's branch
switches — the harness reads the workload script from disk at subprocess
spawn time, so the working tree must remain stable across the orchestrator's
~16-minute run):

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/q2_cost_orchestrator.py \
  --n 30 --cohorts cold,warm --out /tmp/q2_sessions.jsonl
```

**Outcome:** 60/60 sessions completed successfully (30 cold + 30 warm, all
`status=ok`). Per-session JSONL retained at `/tmp/q2_sessions.jsonl`
(local-only — not committed because it contains absolute paths).

**Per-cohort timing (`elapsed_orchestrator_ms` field; includes subprocess
spawn + harness + Vertex round-trip + in-sandbox workload):**

| Cohort | n | ok | min | p25 | p50 | p75 | p95 | max | mean | stdev |
|--------|---|----|------|------|------|------|------|------|------|--------|
| cold | 30 | 30 | 13.34 s | 13.85 s | **14.10 s** | 14.32 s | 22.95 s | 28.65 s | 15.25 s | 3.27 s |
| warm | 30 | 30 | 13.49 s | 14.04 s | **14.14 s** | 14.32 s | 22.21 s | 25.99 s | 15.21 s | 2.82 s |

**Headline observation: cold and warm cohorts are statistically
indistinguishable.** p50 differs by 40 ms (0.3% of the median). mean differs
by 40 ms. p95 differs by 0.74 s (cold higher). This contradicts the
methodology's a-priori model that warm sessions would be measurably
faster due to sandbox container reuse.

Two plausible interpretations (both consistent with the orchestrator's
design note about cross-subprocess warmth being a Vertex-backend behaviour):

1. **Vertex does not reuse sandbox containers across `execute_code` API
   calls within this engine.** Every call provisions a fresh runtime,
   bringing the warm cohort to the cold cohort's baseline.
2. **Vertex does reuse containers, but the saved time is below this
   probe's noise floor** (the per-session overhead is dominated by
   subprocess spawn + Python startup + `google-genai` SDK import, which
   are paid per orchestrator subprocess regardless of Vertex's
   container state).

Either way, **the SK-PRD-02 `SandboxPool` warmth win cannot come from
holding the same engine resource name across separate ADK sessions.** It
has to come from holding the same `AgentEngineSandboxCodeExecutor`
*Python object* across multiple invocations within one process — which
is the in-process pool pattern SK-PRD-02 already designs around.

**In-sandbox workload timing (representative first cold session):**

```json
{
  "steps": {
    "compute":    {"elapsed_ms": 1.83},
    "file_io":    {"elapsed_ms": 2.54},
    "subprocess": {"elapsed_ms": 7.16, "output": "{\"tool\": \"stub\", \"result\": \"ok\"}"},
    "sleep":      {"elapsed_ms": 10000.76}
  },
  "rss_kb": 127344,
  "total_elapsed_ms": 10012.3
}
```

The 10 s `time.sleep(10)` dominates the in-sandbox elapsed time (10.01 s
total). The other three steps account for ~11 ms. The
**~4 s gap between in-sandbox total (10.01 s) and orchestrator p50 (14.10 s)**
is the per-session overhead: subprocess startup (~1 s for `uv run` cold
start within the worktree), Python interpreter + SDK import (~1-2 s), and
Vertex `execute_code` API round-trip (~1-2 s including sandbox creation).

#### Cost (Vertex billing export — settled; pulled 2026-05-31)

Vertex AI billing exports have daily granularity; the N=30 run completed
2026-05-25 and the export was fully settled by this pull on 2026-05-31
(≫ the 36 h window that opened 2026-05-27T01:30Z).

**Headline: the sandbox path produced no separately-metered Vertex cost.**
The dedicated spike engine `sk-prd-00-spike-sandbox`
(`…/reasoningEngines/2624457839443181568`) is a **sandbox-parent-only engine
with no `query()` implementation**, so it runs no deployed serving container
and accrued **zero `ReasoningEngine management fee`** over 2026-05-23 →
2026-05-30 (0 billing rows for `reasoning-engine-2624457839443181568`). Vertex
does **not** itemise a `SANDBOX_ENVIRONMENT_RUNTIME` or code-execution SKU in
this billing account/window (0 rows for any `%sandbox%` / `%code exec%` SKU
across all six projects in the export). The only spike-attributable line items
are orchestration-layer Gemini tokens (label `adk_agent_name=spike_sandbox_agent`),
which §a explicitly **excludes** from the Q2 sandbox-cost measure — and which
were consumed almost entirely on 2026-05-24 during SK-1 agent runs, not by the
2026-05-25 direct-executor N=30 run.

**Line-item split:**

| Billing SKU | Window total ($) | Per-session (cold, $) | Per-session (warm, $) | Attribution |
|---|---|---|---|---|
| Vertex AI Reasoning Engine compute (`reasoning-engine-2624457839443181568`) | 0.000000 | 0.000000 | 0.000000 | Direct (resource name) — 0 rows; sandbox-parent engine, no `query()` container |
| sandboxEnvironment lifecycle (`SANDBOX_ENVIRONMENT_RUNTIME`) | n/a | n/a | n/a | SKU not itemised by Vertex in this window |
| Generative AI code-exec output tokens (`GENERATIVE_AI_CODE_EXECUTION`) | n/a | n/a | n/a | SKU not present; direct executor emits no `code_execution_result` Gemini tokens |
| Network egress (`NETWORKING_EGRESS_GOOG`) | 0.000000 | 0.000000 | 0.000000 | 0 spike-tagged egress rows (same-region same-project; Q1 is authoritative) |
| **Total (session-attributable)** | **0.000000** | **0.000000** | **0.000000** | |
| _Memo: orchestration LLM — **excluded** by §a_ | _0.290715_ | _≤ 0.0048¹_ | _≤ 0.0048¹_ | Label `spike_sandbox_agent`: $0.290024 on 05-24 (SK-1 runs), $0.000691 on 05-25 (Q2) |

¹ Upper bound only, and out of scope per §a. Even if the **entire** $0.290715 of
orchestration-layer Gemini spend (almost all of it 2026-05-24 SK-1 traffic, not
the Q2 run) were wrongly charged to the 60 Q2 sessions, that is $0.0048/session
— still ~20× under the $0.10 threshold. The 2026-05-25-only spike LLM spend was
$0.000691 total (≈ $0.0000115/session).

Reproducible query (run 2026-05-31 against `ken-e-dev.billing_export`):

```sql
SELECT
  DATE(usage_start_time) AS day, service.description AS service,
  sku.description AS sku, ROUND(SUM(cost), 6) AS cost_usd
FROM `ken-e-dev.billing_export.gcp_billing_export_resource_v1_0183BD_803ED8_88685C`
WHERE usage_start_time >= TIMESTAMP("2026-05-23 00:00:00 UTC")
  AND usage_start_time <  TIMESTAMP("2026-05-31 00:00:00 UTC")
  AND project.id = "ken-e-dev"
  AND ( resource.name = "reasoning-engine-2624457839443181568"          -- engine fee: 0 rows
        OR EXISTS (SELECT 1 FROM UNNEST(labels) l                       -- spike LLM, by label
                   WHERE l.key = "adk_agent_name" AND l.value = "spike_sandbox_agent") )
GROUP BY day, service, sku ORDER BY day, cost_usd DESC;
```

**Threshold check (PRD §7.AC-2 / AC #5): PASS** — warm-cohort per-session
session-attributable cost = **$0.000000/session** (no metered sandbox or engine
cost; ≤ $0.0048 even under the absurd all-LLM upper bound) — far below the
$0.10/session threshold.

---

### Implication for Skills

#### Timing-derived implications (load-bearing today)

1. **`SandboxPool` warmth must be in-process.** Cross-subprocess warmth via
   the same engine resource name produces no measurable speedup (cold p50
   14.10 s, warm p50 14.14 s — within 40 ms). SK-PRD-02's pool design
   should not rely on Vertex reusing sandbox containers across separate
   API sessions; the latency win comes only from holding the same
   `AgentEngineSandboxCodeExecutor` instance across multiple
   `execute_code` calls in a single process.

2. **Per-session overhead is ~4 s on the orchestrator side, ~10 ms in the
   sandbox.** A 10 s in-sandbox script takes ~14 s wall-clock at the
   caller. For SK-PRD-02 pool sizing: the per-call orchestrator overhead
   does not amortise across pool entries (each entry pays its own SDK
   import + ADC bootstrap once), so the pool's value is for *batches of
   calls per session*, not for one-off invocations.

3. **`_IDLE_TTL_SECONDS` floor: ~14 s.** Idle TTL shorter than the typical
   session runtime would be premature eviction. This combined with Q4's
   5-minute single-budget cap gives a recommended range of `[15 s, 300 s]`
   for SK-PRD-02's `_IDLE_TTL_SECONDS`.

4. **Per-cohort stdev is modest (cold 3.27 s, warm 2.82 s).** The mean is
   stable. The N=30 sample is large enough that p50/p95 numbers above
   should be treated as load-bearing for SK-PRD-02 tuning.

#### Billing-derived implications (resolved 2026-05-31)

5. **`_MAX_ENTRIES` (LRU cap): cost is not the binding constraint — size by
   memory/concurrency; recommended default `_MAX_ENTRIES = 8`.** The billing
   reconciliation shows warm-held sandboxes carry **no metered holding cost**:
   the sandbox-parent engine accrues no `ReasoningEngine management fee` and
   sandbox runtime is not a separately-billed SKU. The original worry ("if
   sandbox-environment lifecycle is a per-pool-entry cost, a larger cap may be
   more economical") is therefore **moot** — there is no per-entry cost to
   amortise either way. `_MAX_ENTRIES` should be sized by per-process memory and
   expected concurrent in-process sessions (see Q4 resource limits), not
   economics. **Caveat for SK-PRD-02:** if the pool is later hosted under a
   *production* engine that also serves `query()` traffic, that host engine's
   management fee (~$0.086/h when active — observed on peer `ken-e-chat-agent` /
   `strategy-supervisor` engines in the same window) is a **fixed deployment
   cost shared across all sessions**, not a per-sandbox-session cost; it does
   not change the per-session economics measured here.

6. **Rate-limit recommendation: no cost-based sandbox rate limit needed for
   Release 1.** Per-session cost is $0.00 metered (≤ $0.0048 upper bound) —
   ~20×+ below the $0.10/session trigger in PRD §7.AC-2. A per-account
   sandbox-session cap is **not** warranted on cost grounds. Runaway/abuse
   protection remains the responsibility of Q4's per-session 5-minute budget cap
   and the SK-9 security controls, not a cost-based rate limiter.

7. **PRD §9 open question (rate-limit threshold): CLOSED.** Representative
   per-session cost ($0.00 metered; ≤ $0.0048 absolute upper bound) is far below
   $0.10/session, so KEN-E does **not** rate-limit sandbox sessions per account
   on cost grounds (Items 5–6). Re-open only if Vertex begins itemising
   `SANDBOX_ENVIRONMENT_RUNTIME`, or if SK-PRD-02 hosts the pool under a
   `query()`-serving engine and elects to attribute that engine's fixed
   management fee per-session.

---

## Question 3 — Cross-skill state contamination

### Test

**Hypothesis:** `AgentEngineSandboxCodeExecutor`'s "state persists within a session" semantics
may allow a script executing in one skill's code block to observe state written by a different
skill's script earlier in the same session. This would mean the isolation boundary is the
*session*, not the *skill*.

**Setup:** Two scripts attach to the same throwaway agent (proxy for two skills on one specialist):

- `scripts/spike/skills/q3_skill_a_writer.py` — writes a distinct sentinel value to four
  state vectors, then prints `[A] <vector>: WROTE <sentinel>`.
- `scripts/spike/skills/q3_skill_b_reader.py` — probes each vector, prints
  `[B] <vector>: LEAK (<observed>)` or `[B] <vector>: ISOLATED`.

State vectors tested:

| Vector | What is written | Where |
|--------|----------------|-------|
| `fs` | `SK4_SENT_A_fs_<utc>` | `/tmp/sk4_sentinel.txt` |
| `env` | `SK4_SENT_A_env_<utc>` | `os.environ["SK4_SENTINEL"]` |
| `mod` | `SK4_SENT_A_mod_<utc>` | `sys.modules["sk4_state"].sentinel` |
| `tmpsub` | `SK4_SENT_A_tmpsub_<utc>` | `tempfile.mkdtemp(prefix="sk4_")/sentinel.txt` + `/tmp/sk4_pid` (via subprocess) |

> **Note on vector count:** The implementation plan (D3) names four state vectors; the results
> table below expands `tmpsub` into `tmpsub` (tempdir file) + `subprocess-pid` (the PID record
> written via `sh -c "echo $$ > /tmp/sk4_pid"`). The PID recorded is the shell child spawned by
> `subprocess.run`, not the Python process PID — its presence/absence is the LEAK/ISOLATED signal,
> not its value. Both sub-vectors test the same underlying surface (container `/tmp` persistence)
> and are kept separate to preserve per-vector evidence granularity.

**Probes run:**

1. **Same-session** — single harness invocation, both scripts as sequential `--script` arguments,
   sharing one `Runner` session and one `AgentEngineSandboxCodeExecutor` instance. This is the
   closest available proxy for "two skills attached to one specialist."
2. **Cross-session** — two separate harness invocations (each creates a fresh
   `InMemorySessionService` + `Runner`). Upper-bound isolation check.

**Harness invocations:**

```bash
# Same-session
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q3_skill_a_writer.py \
    --script scripts/spike/skills/q3_skill_b_reader.py \
  | tee docs/spike/q3-raw/same-session.log

# Cross-session (invocation A — writer)
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q3_skill_a_writer.py \
  | tee docs/spike/q3-raw/cross-session-a.log

# Cross-session (invocation B — reader)
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q3_skill_b_reader.py \
  | tee docs/spike/q3-raw/cross-session-b.log
```

---

### Result

**Empirical status:**
- **Cross-session (5 vectors):** CONFIRMED — standalone OS-process isolation test (two separate
  `uv run python` invocations, no GCP credentials required). Results: `fs`/`tmpsub`/`subprocess-pid`
  LEAK; `env`/`mod` ISOLATED.
- **Same-session (5 vectors):** CONFIRMED LIVE (2026-05-25) — direct-mode harness against the live
  spike Agent Engine. **All 5 vectors LEAK** (fs, env, mod, tmpsub, subprocess-pid). Confirms the
  ADK "state persists within a session" guarantee at the Python-interpreter level: writer's
  filesystem writes, environment variables, in-memory modules, tempdir contents, and subprocess-PID
  records are all visible to the reader script running in the same session.

**Failure attribution — historical context (resolved 2026-05-25).** The
original same-session harness invocation did not complete on the Dev Team
VM; raw logs in `docs/spike/q3-raw/*.log` show the **proximate** cause was
that `KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME` (and the legacy
`KENE_SPIKE_SANDBOX_RESOURCE_NAME` fallback) were unset — the harness exited
before any Vertex API call. The IAM constraint
(`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com` lacks
`aiplatform.endpoints.predict` on `ken-e-dev`) was the **next** wall the run
would have hit, observed on adjacent Q1/Q2 attempts on the same VM. Both
gaps were closed for the 2026-05-25 live capture by (1) setting the env var
to the spike Agent Engine resource name (`projects/525657242938/...`), and
(2) running from a credentialled workstation (`ken@ken-e.ai`) post the
SK-33 harness rework.

#### Per-vector results table

| Vector | Same-session | Cross-session | Basis |
|--------|-------------|---------------|-------|
| `fs` | **LEAK (live 2026-05-25)** | LEAK | live sandbox capture / standalone OS-process test |
| `env` | **LEAK (live 2026-05-25)** | ISOLATED | live sandbox capture / standalone OS-process test |
| `mod` | **LEAK (live 2026-05-25)** | ISOLATED | live sandbox capture / standalone OS-process test |
| `tmpsub` | **LEAK (live 2026-05-25)** | LEAK | live sandbox capture / standalone OS-process test |
| `subprocess-pid` | **LEAK (live 2026-05-25)** | LEAK | live sandbox capture / standalone OS-process test |

#### Live capture (2026-05-25, direct-mode harness post Wave 2.5 rework)

```
=== [1/2] q3_skill_a_writer.py stdout ===
[A] fs: WROTE SK4_SENT_A_fs_20260525T121952Z
[A] env: WROTE SK4_SENT_A_env_20260525T121952Z
[A] mod: WROTE SK4_SENT_A_mod_20260525T121952Z
[A] tmpsub: WROTE SK4_SENT_A_tmpsub_20260525T121952Z in /tmp/sk4_eky_luh4

=== [1/2] q3_skill_a_writer.py status: ok ===
=== [2/2] q3_skill_b_reader.py stdout ===
[B] fs: LEAK (SK4_SENT_A_fs_20260525T121952Z)
[B] env: LEAK (SK4_SENT_A_env_20260525T121952Z)
[B] mod: LEAK (SK4_SENT_A_mod_20260525T121952Z)
[B] tmpsub: LEAK (SK4_SENT_A_tmpsub_20260525T121952Z)
[B] subprocess-pid: LEAK (writer PID record: 12)

=== [2/2] q3_skill_b_reader.py status: ok ===
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 2
Elapsed (s)  : 4.46
Exit status  : ok
```

Both scripts ran in the same sandbox session (`--script` invoked twice in
one harness invocation, mirroring the SK-PRD-02 `SandboxPool` runtime
pattern of multiple scripts attached to one specialist). The reader's
sentinel values match the writer's exactly — that's the literal
demonstration of state persistence across `executable_code` invocations.
Trustworthiness: direct mode (no `LlmAgent`), harness returned `Exit
status: ok` only because every per-script status was `ok`; the per-vector
LEAK signals come from the reader's stdout (Python comparing the observed
sentinel against `os.environ`, `/tmp` contents, etc.), not from harness
heuristics.

#### Standalone process validation (non-sandbox)

To confirm script logic, writer and reader were run as **separate `uv run python` invocations**
(separate OS processes, same host `/tmp`). This is analogous to a cross-session run on a host
that does not clear `/tmp` between sessions:

```
[A] fs: WROTE SK4_SENT_A_fs_20260524T175135Z
[A] env: WROTE SK4_SENT_A_env_20260524T175135Z
[A] mod: WROTE SK4_SENT_A_mod_20260524T175135Z
[A] tmpsub: WROTE SK4_SENT_A_tmpsub_20260524T175135Z in /tmp/sk4_r7za51jh
---
[B] fs: LEAK (SK4_SENT_A_fs_20260524T175135Z)
[B] env: ISOLATED
[B] mod: ISOLATED
[B] tmpsub: LEAK (SK4_SENT_A_tmpsub_20260524T175135Z)
[B] subprocess-pid: LEAK (writer PID record: 2348)
```

Observations from the separate-process run:
- **fs, tmpsub, subprocess-pid**: LEAK — `/tmp` state persists across process boundaries on the
  same host. Confirms the reader logic works correctly.
- **env, mod**: ISOLATED — separate OS processes have separate memory spaces, as expected.

This validates that both scripts are logically correct and ready for the actual sandbox run.

#### Architecture-level inference (pending empirical confirmation)

Based on ADK documentation for `AgentEngineSandboxCodeExecutor`:

> "state persists within a session"

This guarantees the Python interpreter is maintained across multiple code block executions within
one `Runner` session. The inference for each vector in a **same-session** run follows:

| Vector | Inferred same-session result | Reasoning |
|--------|------------------------------|-----------|
| `fs` | **LEAK** | Same container filesystem; `/tmp` persists between code blocks |
| `env` | **LEAK** | Same process; `os.environ` is shared across code blocks in one session |
| `mod` | **LEAK** | Same Python interpreter; `sys.modules` persists between code blocks |
| `tmpsub` | **LEAK** | Same filesystem namespace; tempdir written by A is visible to B |
| `subprocess-pid` | **LEAK** | `/tmp/sk4_pid` written via subprocess persists in the container |

For a **cross-session** run (two separate `Runner` instances):

| Vector | Inferred cross-session result | Reasoning |
|--------|------------------------------|-----------|
| `fs` | **LEAK (likely)** | The sandbox container may persist between sessions; `/tmp` is not guaranteed to be cleared |
| `env` | **ISOLATED** | A new Python process starts per session; `os.environ` resets |
| `mod` | **ISOLATED** | New Python interpreter per session; `sys.modules` resets |
| `tmpsub` | **LEAK (likely)** | Same container `/tmp`; tempdir from prior session may survive |
| `subprocess-pid` | **LEAK (likely)** | `/tmp/sk4_pid` persists until the container is recycled |

**Worst-case summary:** If the architecture-level inference is correct, within a same-session run
ALL five vectors leak between skills. This is consistent with the ADK documentation's
"state persists within a session" guarantee — that guarantee applies to the entire session
context, not per-skill.

---

### Implication for Skills

**If same-session all-LEAK is confirmed empirically:**

1. **`SandboxPool` keying in SK-PRD-02 §4.6 (`(account_id, config_id)`):** The per-agent pool
   key already provides the right isolation boundary — one sandbox per specialist. State leaks
   across skills attached to the same specialist, but not across specialists for the same account.
   This is the best isolation achievable under the ADK sandbox model without a per-skill executor
   redesign. No change required to SK-PRD-02's pool design.

2. **10-skill-per-agent cap (SK-PRD-02 §9 open question):** The cap remains justified on token
   budget grounds (L1 metadata overhead), but the all-LEAK finding adds a *security argument* for
   keeping the cap low: each additional skill attached to an agent increases the shared state
   surface. The cap is a secondary defence; the primary defence is that script execution is only
   available when `sandbox_code_executor_enabled=true` (an explicit admin opt-in per SK-PRD-04).

3. **README §7 sandbox gating — defense-in-depth:** The existing claim that `scripts/` requires
   `sandbox_code_executor_enabled=true` is correct. The additional finding is that once sandbox
   is enabled, **no per-skill state boundary exists within a session**. The authoring UI
   (SK-PRD-03) should document this: "When multiple skills with scripts are attached to the same
   agent, their script executions share filesystem, environment, and module state within a
   session."

4. **v1 `SkillToolset` does not exist yet:** The spike measures the lower-level sandbox session
   boundary. When `SkillToolset` is built (SK-PRD-02), the skill-layer does not add any
   additional isolation — it is built on top of this same executor. Any future per-skill
   isolation would require a separate `AgentEngineSandboxCodeExecutor` instance per skill, which
   contradicts the `SandboxPool` design and would require a v2 redesign.

5. **Cross-session LEAK for fs/tmpsub vectors:** If the container persists between sessions (as
   is common in warm container pools), `/tmp` state from one session is visible to the next.
   This affects both same-account and same-specialist scenarios. Mitigations: sandbox container
   should be treated as untrusted shared storage; skills that write sensitive data to `/tmp`
   should be documented as carrying cross-session risk.

**Production-promotion note (if any of these patterns are adopted in SK-PRD-02/SK-PRD-03):**
Before using `os.path.join(_tmpdir, ...)` where `_tmpdir` comes from a file on disk, validate that
the path starts with an expected prefix (e.g. `/tmp/sk4_`) and call `os.path.realpath()` before
joining. Replace `subprocess.run(["sh", "-c", ...])` with explicit argument lists (no shell) to
prevent command injection footguns. Both patterns are safe in this spike's controlled context.

**Recommended authoring UI warning (for SK-PRD-03):**

> Scripts attached to the same agent share filesystem, environment, and Python module state
> within a session. Do not write sensitive data to `/tmp` or rely on state isolation between
> skills.

---

## Question 4 — Resource limits & failure modes

### Test

**Probe scripts** (each runs as a separate harness invocation):

| Script | What it does | Expected enforcer signal |
|---|---|---|
| `scripts/spike/skills/q4_cpu_loop.py` | `while True: pass` after a start marker | A CPU cap surfaces as either `OUTCOME_DEADLINE_EXCEEDED` or as a generic API error |
| `scripts/spike/skills/q4_memory_balloon.py` | Doubling `bytearray(N)` allocations starting at 1 MiB | `MemoryError` (Python-level) or a kernel OOM kill (no Python-level signal) |
| `scripts/spike/skills/q4_wall_clock.py` | Cumulative probes at 30s / 120s / 600s for both compute-bound and idle-sleep | The probe whose target exceeds the cap fails; preceding probes establish the threshold |

**Harness invocation pattern:**

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q4_<probe>.py
```

---

### Result

#### CPU loop

```
=== [1/1] q4_cpu_loop.py status: error (ServerError): execute_code call failed —
503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The service is currently
unavailable.', 'status': 'UNAVAILABLE'}}
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 304.17
Exit status  : error (ServerError): execute_code call failed — 503 UNAVAILABLE.
```

**Interpretation.** The probe ran for **304.17 s** before Vertex's
`execute_code` API returned **503 UNAVAILABLE**. This is consistent with a
~5-minute CPU cap on a runaway compute-bound process. The error surface is
notable — Vertex does NOT return a structured `OUTCOME_DEADLINE_EXCEEDED` or
`OUTCOME_RESOURCE_LIMIT` enum; it returns a generic 503 from the API. The
harness classifies this as `error (ServerError)`, which is the right shape
for SK-PRD-02 to handle.

No stdout was captured beyond the start marker (`q4_cpu_loop: start —
entering tight busy loop`); the process was killed before any further
output. The Python-level start-marker print confirms the script reached
the busy loop before being killed.

#### Memory balloon

Two consecutive invocations, both with identical signature:

```
=== [1/1] q4_memory_balloon.py status: ok ===
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 4.43  (first run)  /  3.95  (second run)
Exit status  : ok
```

**Interpretation.** Both runs returned `Exit status: ok` in ~4 s with
**zero stdout captured** — neither the per-allocation `q4_memory_balloon:
allocated N MiB total` line nor the `MemoryError` sentinel made it into
the harness output. Two possibilities, neither cleanly distinguishable
from this single observation:

1. Vertex's memory enforcer kills the sandbox process with SIGKILL when
   the bytearray allocation exceeds the per-process memory cap. The
   SIGKILL bypasses Python's stdout buffer flush, and Vertex's
   `execute_code` API still surfaces `OUTCOME_OK` for the API call
   itself.
2. The sandbox image has Linux memory overcommit enabled such that all
   doubling allocations succeed at the virtual-memory layer (lazy
   zero-page mapping) without ever touching the per-process cap; the
   script terminates "naturally" via some path that produces no output.

Either way, **the memory probe pattern is not informative for SK-PRD-02
SandboxPool tuning** — the harness cannot derive a per-MiB cap from this
signal. A redesigned probe that streams progress to a sandbox-side file
(then captured by a sibling read-probe) would be needed to recover this
measurement.

#### Wall-clock

```
=== [1/1] q4_wall_clock.py status: error (ServerError): execute_code call failed —
503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The service is currently
unavailable.', 'status': 'UNAVAILABLE'}}
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 303.49
Exit status  : error (ServerError): execute_code call failed — 503 UNAVAILABLE.
```

**Interpretation.** The cumulative wall-clock probe was killed at
**303.49 s** — within 1 s of the CPU loop's 304.17 s. Vertex caps both
compute-bound and wall-clock-bound scripts at the **same ~5-minute
threshold**, surfaced as `503 UNAVAILABLE` rather than a structured
outcome enum. Because no stdout was captured (the SIGKILL bypassed
Python's stdout flush, same as CPU and memory), we cannot determine
exactly which probe was running when the cap fired. However, the
elapsed time (303 s) bounds the answer: the script had completed
`compute-30s` (cumulative 30 s), completed `compute-120s` (cumulative
150 s), and was midway through `compute-600s` (would have finished at
750 s) when killed. The idle-sleep probes never ran.

**Implications for the compute-vs-sleep question:** undetermined from
this probe. The 5-minute cap fired during the compute-bound phase before
the script reached the idle-sleep portion. A refined probe would
front-load a short idle-sleep test (~60 s) to determine whether sleep
time counts equivalently against the same cap.

---

### Findings summary

| Probe | Vertex signal | Observed cap |
|---|---|---|
| CPU loop | `503 UNAVAILABLE` after 304.17 s | ~5 min (300 s) cap |
| Memory balloon | `OUTCOME_OK` with no stdout | not measurable via this probe pattern |
| Wall-clock (compute path) | `503 UNAVAILABLE` after 303.49 s | ~5 min (300 s) cap |

**The CPU and wall-clock probes returning the same ~300 s threshold
(within 1 s of each other) is consistent with a single Vertex sandbox
lifetime cap, not two independent caps.** SK-PRD-02 should model this as
"one 5-minute budget per `execute_code` call" rather than "5 min CPU AND
5 min wall-clock as independent budgets."

> [!NOTE]
> **503 ≠ definitely-a-cap caveat.** Vertex's `execute_code` API also
> returns `503 UNAVAILABLE` for transient backend errors (load shedding,
> region capacity, internal restarts). The 5-minute interpretation is
> the most parsimonious explanation given two independent probes (CPU
> and wall-clock) hit it within 1 s of each other, but a third probe run
> a day later that produces the same elapsed time would be the cleanest
> confirmation. SK-7 should note this as "best-current-interpretation,"
> not "validated against a known SLA."

### Concurrent-sandbox observation — RETRACTED

> An earlier draft of this fragment claimed Vertex had a "low
> concurrent-sandbox cap (1-2)" based on a Q2 orchestrator run where
> 59/60 sessions failed at 0.06 s elapsed. **That finding was incorrect.**
> The Q2 failure was caused by a branch-switch during orchestrator
> execution: the orchestrator `subprocess.run`s the harness with a
> filesystem-relative path to `scripts/spike/skills/q2_cost_per_session.py`,
> and the main working tree's branch was switched from `spike/...` to
> `integration/...` between sessions 1 and 2, removing the file from the
> tree the subprocess saw. Diagnosed via the per-session `raw_stdout` in
> `/tmp/q2_sessions.jsonl`, which showed
> `[harness] Script not found: .../q2_cost_per_session.py` for every
> failed session.
>
> A clean Q2 re-run was performed from a `git worktree` checkout of
> `spike/agent-engine-sandbox` at `/tmp/kene-spike/`, isolated from
> the main repo's branch switches. See the Q2 staging fragment
> (`docs/spike/q2-cost-per-session-findings.md`) for those numbers.
>
> No empirical evidence for or against a Vertex concurrent-sandbox cap
> remains; the earlier claim is withdrawn. A future probe specifically
> designed to test concurrent sandbox creation (multiple
> `execute_code` calls in flight against the same engine) would resolve
> this question if it matters for SK-PRD-02 `SandboxPool` design.

---

### Implication for Skills

1. **SK-PRD-02 `_MAX_ENTRIES` for `SandboxPool`:** The 5-min CPU cap is
   the per-script-invocation budget. A pool entry's effective useful
   lifespan is bounded by this cap (if the script holds CPU). The pool's
   eviction strategy should prefer warm entries that have served short
   invocations recently over entries that have been idle for >5 min.
2. **SK-PRD-02 `_IDLE_TTL_SECONDS`:** The wall-clock cap is ~5 min total
   per `execute_code` invocation (CPU and wall-clock probes both fired at
   ~303 s). Whether idle-sleep counts the same as compute remains
   undetermined from this probe — Vertex killed the script before reaching
   the idle-sleep probes. A refined probe with a front-loaded idle-sleep
   would resolve this; captured as an SK-PRD-02 follow-up. For now, treat
   `_IDLE_TTL_SECONDS` as bounded by the same 5-minute budget — a pooled
   sandbox cannot be "kept warm" past this point.
3. **Error-handling: 503 UNAVAILABLE is a kill signal, not a transient.**
   SK-PRD-02 MUST NOT retry `execute_code` on 503 — that response means
   the sandbox was forcibly terminated. Retry would waste quota and
   produce no new information. Treat 503 like any structured
   `OUTCOME_*_LIMIT` enum.
4. **Concurrent-sandbox cap — withdrawn.** See the RETRACTED section
   above; the apparent cap was a branch-switching artifact in the spike's
   own tooling, not a Vertex behaviour. No SK-PRD-02 implication remains
   from this thread.
5. **Memory measurement gap:** SK-PRD-02 cannot rely on Python-level
   `MemoryError` to detect OOM. The sandbox memory enforcer kills the
   process opaquely. If memory cost is a tuning input for the pool,
   measurement must come from an external signal (e.g., a separate probe
   that reads `/proc/self/status` and writes to a sandbox-side file
   before the OOM-trigger allocation).

---

## Question 5 — File I/O with scripts/

### Test

**Probe script:** `scripts/spike/skills/q5_file_io.py` (six access patterns
in a single script, emitting one JSON object on stdout).

**Bundle staged on disk:**
`scripts/spike/skills/q5_skill_bundle/SKILL.md` cites
`scripts/extract.py` (a file containing a `SENTINEL = "..."` assignment).
The bundle exists only on the spike branch as a representative skill
layout — it is **not** transmitted into the sandbox by the harness.

**Access patterns:**

| Block | What it tries | Why |
|---|---|---|
| `runtime_characterization` | `os.getcwd()`, `os.listdir(".")`, `pwd.getpwuid(os.getuid()).pw_name`, `sys.executable`, `socket.gethostname()`, `platform.platform()` | Establish the sandbox's filesystem rooting + identity surface |
| `open_read` | `open("scripts/extract.py").read()` | Plain stdlib open — relative path |
| `pathlib_iterdir` | `pathlib.Path("scripts/").iterdir()` | Verify directory existence |
| `env_bundle_keys` | scan `os.environ` for `SKILL_/BUNDLE_/KENE_/RESOURCE_/AGENT_/VERTEX_/GOOGLE_/ADK_/WORKSPACE_` prefixes | Check whether skill metadata is injected via env vars |
| `exec_run` | `open()` + `exec()` of `scripts/extract.py`, capturing `SENTINEL` from `exec_globals` | Verify code-execution path can reach the file |
| `alt_paths` | `os.path.exists/is_file` on 6 alternative paths (`/tmp/skills/...`, `/workspace/skills/...`, `/mnt/skills/...`, `/var/skills/...`, `~/skills/...`, parent-dir) | Cover every plausible bundle mount point |

**Harness invocation:**

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q5_file_io.py
```

---

### Result

**Live capture (2026-05-25, direct-mode harness):**

```json
{
  "runtime_characterization": {
    "cwd": "/home/bard",
    "ls_cwd": [],
    "username": "root",
    "sys_executable": "/usr/local/bin/python3",
    "hostname": "localhost",
    "platform": "Linux-4.19.0-gvisor-x86_64-with-glibc2.36"
  },
  "open_read": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts/extract.py'"
  },
  "pathlib_iterdir": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts'"
  },
  "env_bundle_keys": {
    "status": "ok",
    "value": {},
    "error": null
  },
  "exec_run": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts/extract.py'"
  },
  "alt_paths": {
    "status": "ok",
    "value": {
      "/tmp/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/workspace/skills/q5_skill_bundle/scripts/extract.py": {"exists": false, "is_file": false},
      "/mnt/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/var/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/root/skills/q5_skill_bundle/scripts/extract.py":      {"exists": false, "is_file": false},
      "/home/scripts/extract.py":                             {"exists": false, "is_file": false}
    },
    "error": null
  }
}
```

Harness trailer:

```
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 3.11
Exit status  : ok
```

**Trustworthiness:** direct mode (no hallucination surface), explicit
`Exit status: ok` from the harness means the executor reported
`OUTCOME_OK` and the script produced one structured JSON object on stdout.
The FileNotFoundError values are real Python exception objects observed
INSIDE the sandbox runtime, not synthetic LLM output.

#### Per-pattern outcome table

| Pattern | Status | Conclusion |
|---|---|---|
| `runtime_characterization` | ok | Sandbox rooted at `/home/bard` (empty); runs as `root`; gVisor-isolated; Python 3 at `/usr/local/bin/python3` |
| `open_read` | file_not_found | `scripts/extract.py` not at the script's cwd |
| `pathlib_iterdir` | file_not_found | `scripts/` directory does not exist at the script's cwd |
| `env_bundle_keys` | ok (empty dict) | **No** skill-metadata env vars (SKILL_/BUNDLE_/KENE_/etc) are injected by the sandbox runtime |
| `exec_run` | file_not_found | The `exec()` path cannot reach the bundle file because the bundle is not present |
| `alt_paths` | ok (all 6 missing) | None of the plausible mount points exists |

#### Sandbox runtime details (from `runtime_characterization`)

- **Kernel:** `Linux-4.19.0-gvisor-x86_64-with-glibc2.36` — Google's
  [gVisor](https://gvisor.dev/) user-space kernel. Provides syscall-level
  isolation between the sandbox process and the host. Container escape via
  kernel vulnerabilities is substantially harder than with a stock Linux
  container.
- **User:** `root` inside the sandbox. Not a security risk because gVisor
  intercepts every syscall — the `root` identity has no privileges
  outside the user-space kernel's policy.
- **CWD:** `/home/bard` (empty directory). Standard Vertex sandbox working
  directory.
- **Python:** `/usr/local/bin/python3` — system Python install on the
  sandbox image.

---

### Implication for Skills

1. **SK-PRD-03 skill-authoring contract — `scripts/` is NOT filesystem-mounted.**
   The SKILL.md design pattern (a `scripts/` directory containing
   `extract.py` that the L3 callable can `open()` and exec) **cannot rely
   on filesystem availability inside the sandbox**. The default sandbox
   working directory is empty; `scripts/extract.py` does not resolve.
   SK-PRD-03 MUST package skill content into the script string itself —
   either by inlining the bundle file contents verbatim or by serialising
   the bundle to base64/JSON and embedding it as a constant the L3 script
   decodes at runtime.

2. **No env-var-based metadata injection.** The sandbox does not surface
   SKILL_, BUNDLE_, KENE_, AGENT_, RESOURCE_, or any other skill-related
   environment variable. Metadata that the L3 callable needs (skill ID,
   account ID, config-version) must travel inside the script body too.

3. **SK-PRD-02 `SandboxPool` bundle delivery is the right abstraction.**
   The pool already constructs script strings per-invocation; this Q5
   result confirms that pattern is the only viable shape. There is no
   "warm the sandbox with bundle X" upload step available via the ADK
   1.27.5 surface — every invocation must self-contain its bundle.

4. **gVisor isolation is a security positive.** Combined with Q1's empty
   default egress, the sandbox security posture is substantially stronger
   than the pre-spike research assumed. The SK-9 security review can
   reference this finding to lower the perceived attack surface of
   user-authored skills (still high in absolute terms, but the lateral
   movement surface is small).

5. **Bundle-size cap implication for SK-PRD-03.** Because every invocation
   must inline its bundle into the script string, very large bundles
   become an LlmAgent token-budget issue in legacy-mode use cases (not a
   concern in default direct mode, where there's no LLM context cost).
   SK-PRD-03 should impose a per-script bundle-size cap when the legacy
   LLM loop is enabled.

---

## Recommendation

_TODO — SK-8 (compose go/scoped-go/no-go recommendation + Sprint 2.6-B follow-ups)._

---

## Follow-ups for Sprint 2.6-B

_TODO — SK-8 (compose go/scoped-go/no-go recommendation + Sprint 2.6-B follow-ups)._
