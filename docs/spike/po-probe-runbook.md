# SK-PRD-00 Wave 2 — PO Probe Runbook

> [!CAUTION]
> **DO NOT RUN THE PROBES.** A harness regression discovered during PR #636
> review means `scripts/spike/sandbox_test_harness.py` cannot reliably produce
> empirical sandbox measurements. See
> [`harness-validation.md`](./harness-validation.md) for the full evidence —
> `Exit status: ok` can coexist with hallucinated content, and the harness
> has no way to tell. Every command in this runbook is suspended until
> Wave 2.5 reworks the harness.
>
> This file is preserved as the eventual-runbook reference: the env vars,
> credential prerequisites, and per-probe procedure are still correct; only
> the underlying harness is broken. **Delete this file when Wave 2 is
> complete (probes captured, staging fragments populated, PR description
> reconciled). Do not delete until then — it carries the live spike Agent
> Engine resource name and the spike service account details.**

## What changed since PR #636 opened

During PR review, the smoke test (`hello.py` through the harness against the
real spike Agent Engine) surfaced that Gemini 2.0 Flash does not reliably
invoke `AgentEngineSandboxCodeExecutor`. The model produces plausible-looking
output drawn from training data:

- Trivial fixture (`print("hello")`): harness correctly reported
  `error: agent emitted no executable_code`.
- Non-trivial fixture with arbitrary-precision math and current timestamp,
  original prompt: reported same error — but only because the math was wrong
  enough to be obvious (`2**63-1` returned in place of `2**73-1`).
- Same non-trivial fixture with a forceful "you MUST invoke the tool"
  system prompt: reported `Exit status: ok` with correct math in one run, but
  a similar canary in the next run also reported `ok` with hallucinated math.

The harness cannot distinguish those two cases. See
[`harness-validation.md`](./harness-validation.md) for the full evidence and
recommended rework scope.

The harness instruction and `hello.py` fixture were briefly modified during
diagnosis and have since been **reverted to the as-shipped state** in PR #636
— the forceful prompt is captured in the validation doc as evidence, not as a
fix.

---

## When the harness is fixed (preserved for Wave 2.5)

The procedure below is the eventual runbook for after Wave 2.5 lands a
trustworthy harness. Until then, **do not execute any of these commands**.

### Prerequisites (one-time)

```bash
# 1. Authenticate ADC against ken-e-dev
gcloud auth application-default login
gcloud config set project ken-e-dev

# 2. Confirm the spike Agent Engine still exists. SK-1 provisioned it; SK-10
#    will delete it. The `gcloud ai reasoning-engines` subcommand does NOT
#    exist in current gcloud — verify via REST instead:
TOKEN=$(gcloud auth application-default print-access-token)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568" \
  | head -10
# Expected: displayName "sk-prd-00-spike-sandbox", non-empty createTime.

# 3. Check out the spike branch (Q2-Q5 probe scripts live there; only Q1 +
#    the harness are on main).
git fetch origin spike/agent-engine-sandbox
git checkout spike/agent-engine-sandbox

# 4. Sync deps against the ADK 1.27.5 pin.
uv sync

# 5. Export the env vars every probe needs.
export GOOGLE_CLOUD_PROJECT=ken-e-dev
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=1
export VERTEX_AI_LOCATION=us-central1
export KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568

# 6. Smoke-test the (reworked) harness end-to-end with the proof-of-execution
#    canary that Wave 2.5 must ship. If this prints unpredictable values that
#    pass external verification, the rest will work.
uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/hello.py
```

**Do not proceed past step 6 if the harness rework has not added an external
verification step.** A clean `Exit status: ok` on the current harness is not
proof of anything (see harness-validation.md).

### Q1 — Network egress (SK-2)

```bash
uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q1_network_egress.py
```

**Paste:** harness output verbatim into the `### Result` section of
`docs/spike/q1-network-egress.md`, replacing the `[PASTE verbatim harness
output here]` placeholder. Populate the per-vector outcome table from the
JSON `outcome` field of each probe line.

**Verify:** re-read the `### Implication for Skills` section against the
live results. If any vector returned `blocked` (unexpected), rewrite the
implications. Remove the `> [!CAUTION]` banner once the section holds.

Time: ~5 minutes (after harness rework).

### Q3 — Cross-skill state, same-session only (SK-4)

Cross-session was already empirically confirmed via host-process test; only
same-session is pending.

```bash
uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q3_skill_a_writer.py \
  --script scripts/spike/skills/q3_skill_b_reader.py \
  | tee docs/spike/q3-raw/same-session.log
```

**Paste:** update the "Per-vector results table" in
`docs/spike/q3-cross-skill-state-fragment.md` — replace each `INFERRED: LEAK`
in the Same-session column with the observed `LEAK` / `ISOLATED` from the
`[B]` lines. Update the Basis column to "live sandbox capture" for those
rows. Remove the `> [!CAUTION]` banner.

Time: ~5 minutes.

### Q4 — Resource limits against the Vertex enforcer (SK-5)

The previous Wave 2 attempt used `--local-limits` mode, which measures Linux
`RLIMIT_CPU` / `RLIMIT_AS` on the host — not the Vertex platform enforcer.
SK-5 AC #5 cannot be satisfied with the local results.

```bash
uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q4_cpu_loop.py

uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q4_memory_balloon.py

uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q4_wall_clock.py
```

**Paste:** finalise the Q4 fragment on the spike branch, then copy to
`docs/spike/q4-resource-limits.md`.

Time: ~15-60 minutes (depends on wall-clock test aggressiveness).

### Q5 — File I/O (SK-6)

```bash
uv run python scripts/spike/sandbox_test_harness.py \
  --script scripts/spike/skills/q5_file_io.py
```

If `q5_skill_bundle/` requires multiple invocations to cover all access
patterns, run each per the script's docstring.

**Paste:** populate the Q5 fragment on the spike branch, then copy to
`docs/spike/q5-file-io.md`.

Time: ~30 minutes.

### Q2 — Cost per session (SK-3) — the long pole

```bash
# Smoke (3 sessions, ~5 min)
uv run python scripts/spike/q2_cost_orchestrator.py \
  --n 3 --cohorts cold,warm

# Bulk (N=30, ~30 min wall-clock)
uv run python scripts/spike/q2_cost_orchestrator.py \
  --n 30 --cohorts cold,warm \
  --out scripts/spike/skills/q2_sessions.jsonl
```

Wait **≥36 hours** for the Vertex AI billing export to settle.

Pull billing export filtered to:
- Service account `ken-e-api@ken-e-dev.iam.gserviceaccount.com`
- SKUs: `REASONING_ENGINE_COMPUTE`, `SANDBOX_ENVIRONMENT_RUNTIME`,
  `GENERATIVE_AI_CODE_EXECUTION`, `NETWORKING_EGRESS_GOOG`
- Window: bulk-run date through bulk-run date + 2 days

Update `docs/spike/q2-cost-per-session-findings.md`:
- Cohort table (p50/p95 wall-clock + $/session)
- Line-item split (SKU breakdown)
- Threshold check vs $0.10/session warm-p50
- `Implication for Skills` (`_MAX_ENTRIES`, `_IDLE_TTL_SECONDS`, rate-limit recommendation)
- Remove the `> [!CAUTION]` banner

Time: ~30 min run + 36 h wait + ~30 min analysis = ~2 days end-to-end. This
is the gating item — if it cannot clear in the current cycle, split it into
its own issue with explicit "blocked on billing settlement" status.

---

## After all probes complete (post Wave 2.5)

1. Verify every staging file has its `> [!CAUTION]` banner removed.
2. Reconcile PR #636 description — change "PASS (testing complete)" to
   reflect live captures.
3. Update Linear — transition SK-2 through SK-6 to Done only after the
   staging fragments hold live numbers.
4. Delete this runbook (`git rm docs/spike/po-probe-runbook.md`).
5. Merge.

## If a probe surfaces a security concern

The Q3 fragment flags "Security Severity: medium" with conditional SK-9
escalation. If any live result reveals a **cross-account** or
**production-agent-default** exposure (not just opt-in sandbox-enabled
agents), escalate immediately to `security@ken-e.ai` per SK-PRD-00 §7 AC #5,
raise severity to high/critical, and do not merge until SK-9 acknowledges.
