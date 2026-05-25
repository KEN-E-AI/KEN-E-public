# Question 1 — Network egress

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

> **SK-7 absorption note:** This file will be pasted verbatim under
> `## Question 1 — Network egress` in
> `docs/spike-agent-engine-sandbox-findings.md`. The `### Result` section
> below holds the live 2026-05-25 capture; the "Live execution
> instructions" subsection lower in the file is preserved for
> reproducibility but is no longer load-bearing (the run has happened).

---

## Question 1 — Network egress

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

Paste the full output (from `{` JSON lines through `Exit status`) as a comment on SK-2.
SK-7 will then incorporate the captured output into this document before merging to
`spike/agent-engine-sandbox`.

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
hallucination surface). `Exit status: ok` means the executor returned a
non-OK-free result; the 4 `blocked` outcomes are real failures observed
INSIDE the sandbox runtime (Python's standard `gaierror`/`OSError`
exceptions, not synthetic LLM output). Wall-clock 8.43 s is consistent
with a real cold-start sandbox creation + script execution.

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

> **Task 5 conditional trigger (resolved):** The trigger fired in the
> direction OPPOSITE to what the implementation plan anticipated. SK-9 should
> still be informed of the finding so it can update its threat model.

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

> **Task 5 conditional trigger:** If live results confirm egress is fully open with
> no mitigation (4/4 vectors `allowed`, VPC-SC "untestable" on `ken-e-dev`), post
> comments on SK-9 and SK-8 per implementation plan Wave 4.
