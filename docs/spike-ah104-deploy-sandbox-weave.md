# ADK 2.0 Deploy + Sandbox + Weave Spike — Go/No-Go Report (AH-104)

**Spike issue:** [AH-104](https://linear.app/ken-e/issue/AH-104)  
**Phase:** 0 — De-risking spike (gates [AH-105](https://linear.app/ken-e/issue/AH-105) — chat-tree pin bump)  
**Prior live basis:** `docs/spike-adk2-supervisor-orchestration-live.md` (AH-99, GO-confirmed)  
**Probe scripts:** `docs/spike-adk2/probe-{8,9,10}-*.py` (live/static) + `spike_deploy.py`  
**Date authored:** 2026-06-03  
**Run environment:** scripts authored; live probes require ADC `ken@ken-e.ai` + `ken-e-dev` access  
**Status:** ✅ **PARTIAL GO** — AC #2 (Chat/Billing parity) and AC #3 (sandbox-on-2.0) VERIFIED; AC #1/#4 (live deploy + session/trace) require manual run with `ken-e-dev` ADC (see §2)

---

## §1 — Verdict

✅ **PARTIAL GO.**

| Unknown | Probe | Status |
|---|---|---|
| Chat/Billing parity on ADK 2.0: `transfer_to_agent` token propagation | `test_chat_billing_parity.py` (TC-6) | ✅ **GO — MERGE BLOCKER resolved**: 24/24 pass; `total_billable=1430` verified for both Mode A (pre-attached) and Mode B (per-turn attach via `AlwaysTrueSubAgentList`) |
| Sandbox on ADK 2.0: `AgentEngineSandboxCodeExecutor` import path + `SandboxPool` constructor contract | Probe 9 (TC-2) | ✅ **GO** — all A1–A4 + B1–B4 assertions pass; import path unchanged from 1.x |
| Live-deploy session/trace shape on a real 2.0 engine | Probes 8 + 10 (TC-3, TC-4) | ⏳ **Manual run required** — Test Team VM lacks `storage.buckets.get` on `gs://ken-e-dev-adk-staging` and `aiplatform.reasoningEngines.get` on `ken-e-dev` (cross-project IAM); see §2 for how to run manually and record evidence |

**AC #2 (Chat/Billing parity) — VERIFIED (with the AH-105 shim applied locally):**
`test_chat_billing_parity.py` run under `.venv-adk2` passes 24/24 including all 10
`TestChatParity`, all 10 `TestBillingParity`, and `TestMultiTurnRouting`. The
`AlwaysTrueSubAgentList` fix in `sub_agent_attacher.py` + `hierarchy.py` resolves the ADK 2.0
zero-token-propagation MERGE BLOCKER confirmed in TC-6. This is the primary gate for AH-105.
**The shim itself is NOT committed in the spike PR (#828)** — it was reverted to keep the PR
spike-only and is recorded as the implementation+CI-verification requirement for AH-105 in
**§3.2.1**.

**AC #3 (Sandbox on ADK 2.0) — VERIFIED:** Probe 9 static verification confirms the
`AgentEngineSandboxCodeExecutor` import path is unchanged from 1.x and `SandboxPool`
constructor contract is preserved under ADK 2.0. See §3.3.

**Live probes 8 and 10 require full `ken-e-dev` GCP credentials** with
`storage.objectAdmin` on `gs://ken-e-dev-adk-staging` and
`aiplatform.reasoningEngines.create` / `.get` on the `ken-e-dev` project.
These permissions are not available to the automated Test Team VM.
See §2 for the manual run procedure and §3 for what to record.

**Routing consequence:** AH-105 (chat-tree pin bump) is unblocked by AC #2 (MERGE BLOCKER
verified). AC #1/#4 live probes should be run manually before or alongside AH-111 (the full
deploy + runbook verification issue). If either live probe exits 1 (NO-GO), the findings
section §3 will capture the exact failure for AH-105 to address.

---

## §2 — How to Reproduce the Live Run

**Prerequisites:**

```bash
# 1. ADC with access to ken-e-dev (agent_engines.create, aiplatform.sessions.*, predict)
gcloud auth application-default login
gcloud config set project ken-e-dev

# 2. Bootstrap the full spike venv from repo root (Python 3.10+ required)
python3.12 -m venv .venv-adk2
.venv-adk2/bin/pip install -r docs/spike-adk2/spike_requirements.txt
.venv-adk2/bin/python -c "from importlib.metadata import version; assert version('google-adk')=='2.0.0'; print('adk 2.0.0 OK')"

# 3. Verify harness loads the real token-accounting modules
.venv-adk2/bin/python -c "
import sys; sys.path.insert(0, 'docs/spike-adk2')
import _live_harness; _live_harness.import_real_modules(); print('OK')
"
```

**Run the probes in order:**

```bash
mkdir -p docs/spike-adk2/results

# Deploy the ephemeral engine (keep it alive for probes 8 + 10)
.venv-adk2/bin/python docs/spike-adk2/spike_deploy.py \
    --project ken-e-dev --location us-central1 --keep \
    2>&1 | tee docs/spike-adk2/results/deploy.log

# Probe 8 — probe turn against the deployed 2.0 agent (live)
.venv-adk2/bin/python docs/spike-adk2/probe-8-deploy-probe-turn.py \
    2>&1 | tee docs/spike-adk2/results/probe8.log
echo "probe-8 exit=$?"

# Probe 9 — sandbox import + local pool round-trip (no live GCP calls)
.venv-adk2/bin/python docs/spike-adk2/probe-9-sandbox-code-exec.py \
    2>&1 | tee docs/spike-adk2/results/sandbox.log
echo "probe-9 exit=$?"

# Probe 10 — live session round-trip + Weave trace check
.venv-adk2/bin/python docs/spike-adk2/probe-10-deploy-session-weave.py \
    2>&1 | tee docs/spike-adk2/results/session-weave.log
echo "probe-10 exit=$?"

# Parity test — Chat/Billing parity under the 2.0 venv (no live GCP calls)
.venv-adk2/bin/python -m pytest app/adk/agents/agent_factory/tests/test_chat_billing_parity.py -v \
    2>&1 | tee docs/spike-adk2/results/parity.log
echo "parity exit=$?"

# Clean up the ephemeral engine
.venv-adk2/bin/python docs/spike-adk2/cleanup_spike_engine.py \
    2>&1 | tee docs/spike-adk2/results/cleanup.log
```

Exit-code contract: **0** = GO; **1** = NO-GO (real finding); **2** = INDETERMINATE
(infrastructure/credentials). Classifier: `_live_harness.classify_exit_code`.

---

## §3 — Probe Results

### §3.1 — Deploy + probe turn (Probe 8)

**Probe script:** `docs/spike-adk2/spike_deploy.py` + `docs/spike-adk2/probe-8-deploy-probe-turn.py`  
**AH-104 AC:** "Given a deployed 2.0 dev agent, engine deploys cleanly and answers a probe turn."  
**Status:** ⏳ **Manual run required** (Test Team VM lacks cross-project IAM)

**Blocker:** The automated Test Team VM service account
(`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) lacks `storage.buckets.get` on
`gs://ken-e-dev-adk-staging` and `aiplatform.reasoningEngines.create` on `ken-e-dev`.
`spike_deploy.py` now exits **2** (infrastructure/credentials) when these errors occur.
A developer with full `ken-e-dev` ADC must run this manually.

**Fix note (iteration 2):** `vertexai.init()` is now wrapped in `try/except` so GCS 403s
are caught and classified as exit 2. A global exception handler matching
`cleanup_spike_engine.py` was also added. `_INFRA_ERROR_MARKERS` now includes `"forbidden"`
and `"does not have"` to catch GCS `Forbidden` errors regardless of message format.

**Expected outcome (for manual run):**
- `spike_deploy.py --keep` calls `agent_engines.create()` with `spike_requirements.txt`
  (pinning `google-adk==2.0.0`) and returns a resource name of the form
  `projects/525657242938/locations/us-central1/reasoningEngines/<NEW_ID>`.
- Probe 8 reads the resource name, sends "Say hello and tell me your name.", and
  asserts non-empty text in the response.

**If the deploy fails:** check `gcloud logging read 'resource.type=aiplatform.googleapis.com/ReasoningEngine' --project ken-e-dev` for the backend error — as documented in AH-PRD-13 §9 risk, transitive dep conflicts surface in Cloud Logging, not local stderr. Capture the error here and set verdict NO-GO for AH-105 until resolved.

---

### §3.2 — Parity on 2.0 (Chat/Billing parity suite)

**Test target:** `app/adk/agents/agent_factory/tests/test_chat_billing_parity.py`  
**AH-104 AC:** "Chat/Billing parity suite passes for current single-specialist behaviour."  
**Status:** ✅ **GO — MERGE BLOCKER resolved** (TC-6: 24/24 pass)

**What was verified (TC-6, run under `.venv-adk2` with `google-adk==2.0.0`):**

- `TestCaptureHarness`: 3/3 pass — stub LLM event shapes are correctly captured.
- `TestChatParity`: 10/10 pass — `SessionTurnAccumulator` delta matches canonical fixture for both Mode A (pre-attached `sub_agents`) and Mode B (per-turn attach via `AlwaysTrueSubAgentList`). `total_billable=1430`, `input_tokens=1050` verified.
- `TestBillingParity`: 10/10 pass — `extract_billable_tokens` sums match canonical fixture for both modes.
- `TestMultiTurnRouting`: 1/1 pass — second user turn routes back to root correctly.

**Root-cause fix that unlocked Mode B:** ADK 2.0's `Runner._run_node_async` calls
`build_node(agent)` which creates a model-copy of the root with `sub_agents=[]`, then
checks `bool(self.agent.sub_agents)` on the **original** root to decide `use_scheduler`.
Without the scheduler, `transfer_to_agent` is intercepted without dispatching the
specialist. The `AlwaysTrueSubAgentList` wrapper on `root.sub_agents` ensures
`bool(sub_agents)` is `True` on the original even before the callback populates it.

---

### §3.2.1 — Production shim required for AH-105 (NOT committed in this spike PR)

> **⚠️ Scope note.** The `AlwaysTrueSubAgentList` shim was **reverted out of the spike PR
> (#828)** so the PR stays true to its "spike artifacts only" scope. The parity result in
> §3.2 was measured locally under `.venv-adk2` **with** the shim applied. The shim is a
> **finding to be implemented and CI-verified by [AH-105](https://linear.app/ken-e/issue/AH-105)**
> (the chat-tree pin bump), not by this spike. The exact diff is recorded below so AH-105 can
> apply it verbatim.

**Why deferring is safe (1.34.1 analysis).** Under the currently-pinned `google-adk==1.34.1`
the shim is **inert**, so leaving it out of the spike PR cannot regress production:

- `_get_transfer_targets()` (`google/adk/flows/llm_flows/agent_transfer.py`) builds targets by
  `result.extend(agent.sub_agents)` — it **iterates** the list and never gates on
  `bool(sub_agents)`. An empty-but-truthy list therefore yields zero transfer targets exactly
  like a plain empty list; transfer is still correctly suppressed. The only `bool(sub_agents)`
  truthiness gate in 1.34.1 (`llm_agent.py`) is a private error-message formatter.
- `BaseAgent.model_config` is `ConfigDict(arbitrary_types_allowed=True, extra='forbid')` —
  `validate_assignment` is **off**, so assigning the `list` subclass is not coerced back to a
  plain `list`; the mechanism works on both 1.34.1 and 2.0.
- `app/adk/agents/agent_factory/tests/test_chat_billing_parity.py` passes **24/24 under 1.34.1
  without the shim** (verified post-revert), confirming behaviour-neutrality on the pinned version.

**Diff to apply in AH-105 (production code):**

```diff
diff --git a/app/adk/agents/agent_factory/hierarchy.py b/app/adk/agents/agent_factory/hierarchy.py
@@ build_hierarchy() — import block @@
     from app.adk.agents.agent_factory.sub_agent_attacher import (
+        AlwaysTrueSubAgentList,
         attach_specialists_before_agent_callback,
     )
@@ build_hierarchy() — before `return root_agent` @@
     logger.info("Built root agent %r.", "ken_e")

+    # ADK 2.0 compatibility: ensure use_scheduler=True in Runner._run_node_async.
+    # The Runner checks bool(self.agent.sub_agents) on the original root to decide
+    # whether to activate DynamicNodeScheduler. Without the scheduler,
+    # transfer_to_agent events are yielded but not dispatched; specialist LLM events
+    # never reach the outer stream (zero Billing/Chat token counts).
+    # AlwaysTrueSubAgentList.__bool__ returns True even when empty, so the scheduler
+    # is always active. build_node().clone() creates a fresh regular [] for the
+    # per-turn clone, which _reconcile then populates in-place per turn.
+    root_agent.sub_agents = AlwaysTrueSubAgentList()
+
     return root_agent

diff --git a/app/adk/agents/agent_factory/sub_agent_attacher.py b/app/adk/agents/agent_factory/sub_agent_attacher.py
@@ after `logger = logging.getLogger(__name__)` @@
+class AlwaysTrueSubAgentList(list):
+    """A list subclass that is always truthy, even when empty.
+    (See full docstring carried in the spike branch history — ADK 2.0 use_scheduler fix.)
+    """
+
+    def __bool__(self) -> bool:
+        return True
+
@@ _attach_locked() — fingerprint early-return guard @@
-    if _applied_state == (account_id, new_fingerprint):
+    # ADK 2.0: a fresh per-turn clone has empty sub_agents; only skip reconcile when
+    # root_agent.sub_agents is already populated, else the empty clone never gets specialists.
+    if _applied_state == (account_id, new_fingerprint) and list(root_agent.sub_agents):
         return
@@ _reconcile() — list update @@
-    root_agent.sub_agents = keep
+    # ADK 2.0: update IN-PLACE so the scheduler's model_copy() shallow-copy holders
+    # (which share the list object) see the per-turn specialists via find_agent().
+    root_agent.sub_agents[:] = keep
     return changed
```

> The full, un-elided source (including the complete `AlwaysTrueSubAgentList` docstring) is
> preserved in the spike branch history at `feat/AH-104-adk2-deploy-sandbox-weave-spike` prior
> to the revert commit — recover it with `git show <revert-commit>^:…` if needed.

**Test hooks (parity test, AH-105):** in `test_chat_billing_parity.py`, add
`from app.adk.agents.agent_factory.sub_agent_attacher import AlwaysTrueSubAgentList` and set
`root.sub_agents = AlwaysTrueSubAgentList()` immediately after each Mode B root is built
(`_capture_mode_b_events` and `TestMultiTurnRouting.test_second_user_turn_returns_to_root`).
Re-apply by hand — the import block now also carries `AsyncIterator`, so the recorded diff's
context lines have drifted.

**CI requirement for AH-105:** once the committed pin is `google-adk==2.0.0`, the existing
`app-adk-tests` step (`deployment/ci/pr_checks.yaml`) runs this parity suite under 2.0, which
verifies the shim. To verify the shim **before** flipping the global pin, add a temporary
parallel job that installs `google-adk==2.0.0` in a separate venv and runs
`test_chat_billing_parity.py`, asserting `total_billable=1430` for Mode B.

---

### §3.3 — Sandbox round-trip (Probe 9)

**Probe script:** `docs/spike-adk2/probe-9-sandbox-code-exec.py`  
**AH-104 AC:** "`AgentEngineSandboxCodeExecutor` + `SandboxPool` path round-trips successfully on 2.0."  
**Status:** ✅ **GO** (TC-2: all A1–A4 + B1–B4 pass)

**What was verified (TC-2, run under `.venv-adk2` with `google-adk==2.0.0`, no live GCP calls):**

- **Leg A — import + pool contract (A1–A4):** `AgentEngineSandboxCodeExecutor` imports cleanly from `google.adk.code_executors.agent_engine_sandbox_code_executor` (path unchanged from 1.x). `SandboxPool.get_or_create(account_id, config_id)` returns a `LeasedSandboxExecutor`; pool is empty before `execute_code` (lazy `_construct`); same-key calls return the same pool entry; two distinct keys produce distinct entries. All match `test_sandbox_pool_runtime_rebuild.py` invariants.
- **Leg B — `AgentEngineSandboxCodeExecutor` constructor (B1–B4):** Constructor accepts `sandbox_resource_name` in the format `reasoningEngines/{id}/sandboxEnvironments/{id}` (ADK 2.0 validates the format at construction; the prior multi-segment `sandboxes/` format was rejected). `execute_code` method is present on the instance. Pool releases the sandbox correctly.

**Unknown deferred to AH-111:** Live code-execution through a sandbox-attached specialist
requires a provisioned sandbox resource in `ken-e-dev`. AH-104's scope is the import-path
and pool-contract unknowns (both resolved above). Live code-execution smoke is AH-111's
job (the full deploy + runbook verification).

**Carry-forward:** SK-PRD-02's `SandboxPool` was designed for ADK 1.x; the pool's
synchronous `_construct` / `lease()` contract is ADK-version-agnostic (it wraps
`AgentEngineSandboxCodeExecutor`, not any ADK runner primitive). No migration is expected.

---

### §3.4 — Live-deploy session round-trip + Weave trace check (Probe 10)

**Probe script:** `docs/spike-adk2/probe-10-deploy-session-weave.py`  
**AH-104 AC:** "Spans round-trip and the session persists/loads via the managed session backend."  
**Status:** ⏳ **Awaiting live run**

**Session round-trip (extends AH-99 probe-5 to live-deploy):**
AH-99 probe-5 confirmed `node_info` + `isolation_scope` survive an
append→`get_session`→reconstruct round-trip on the dev backend (stored-event path).
Probe 10 extends this to the **live-deploy path**: sends a turn to the ephemeral engine,
captures `user_id` + `session_id`, and retrieves the session via `VertexAiSessionService`
to verify events are present.

**Weave trace check (non-blocking per AH-PRD-13 §9):**
- Probe 10 calls `init_weave_if_needed(required=False)` and records True/False.
- If True: verifies a `@safe_weave_op` span is emitted and checks whether the
  `google.genai` LLM-call autopatch produces a span.
- If False: records the reason (expected: missing `WANDB_API_KEY` in the spike venv).
- **Either outcome is acceptable** — AH-PRD-13 §9 explicitly classifies weave-autopatch
  fragility as "record, don't block."

**Weave autopatch carry-forward (from AH-99 + AH-PRD-13 §9):** The `google.genai`
LLM-call span has historically been absent when ADK's model client patches the genai
library through environment-based routing (no explicit `Client(vertexai=True, ...)`).
AH-104 records the current state of this on the 2.0 deployed path; the absence is
non-blocking for AH-105.

---

## §4 — Resolved Unknowns Table

| Unknown | Resolution | Evidence |
|---|---|---|
| Chat/Billing parity on ADK 2.0 (`transfer_to_agent` + `AlwaysTrueSubAgentList`) | ✅ **VERIFIED** | TC-6: 24/24 pass under `.venv-adk2`; `total_billable=1430` Mode A = Mode B; MERGE BLOCKER resolved |
| `AgentEngineSandboxCodeExecutor` import path on ADK 2.0 | ✅ Unchanged | TC-2 Leg B: import succeeds, `execute_code` present |
| `SandboxPool` constructor contract on ADK 2.0 | ✅ Preserved | TC-2 Leg A: `get_or_create` returns wrapper, pool empty before `execute_code`, same-key reuse confirmed |
| Live-deploy session/trace shape on a real 2.0 engine | ⏳ Manual run required | Probe 8 + Probe 10 (scripts ready; IAM blocks automated run) |
| Weave autopatch for `google.genai` on ADK 2.0 | ⏳ Manual run required | Probe 10 Weave leg (non-blocking; carry-forward per AH-PRD-13 §9) |

---

## §5 — Recommendations for AH-105 Onwards

1. **Run live probes before merging AH-105.** Probes 8 and 10 are the live gate. Once they
   exit 0, update this document's §1 verdict to GO and proceed with the AH-105 pin bump.

2. **`spike_requirements.txt` is the template for `app/adk/requirements.txt` on 2.0.**
   The file resolves the full runtime dep surface needed by `build_hierarchy()` +
   `agent_engines.create()`. When AH-105 bumps the committed `requirements.txt` pin, use
   `spike_requirements.txt` as the baseline (same packages, change `google-adk==2.0.0`).

3. **Sandbox is not a blocker for AH-105.** The import-path and pool-contract unknowns are
   resolved (Probe 9 GO). Live code-execution belongs to AH-111 (the full deploy + runbook
   verification wave).

4. **Weave autopatch absence is non-blocking.** If Probe 10 reports the `google.genai`
   LLM-call span absent, record it as a known carry-forward per AH-PRD-13 §9 and proceed.
   The `@safe_weave_op` decorator spans are the primary MER-E signal; the genai autopatch
   span is supplementary.

5. **Watch for the `requirements.txt`-staging hazard (AH-PRD-13 §9 risk).** If
   `agent_engines.create()` in Probe 8 / `spike_deploy.py` returns a 500 or the engine
   fails to come online, check Cloud Logging for the backend error before treating it as
   an infra/credentials INDETERMINATE. A transitive dep conflict surfaces there, not locally.

---

## §6 — References

- **Spike issue:** [AH-104](https://linear.app/ken-e/issue/AH-104)
- **Prior live basis:** `docs/spike-adk2-supervisor-orchestration-live.md` (AH-99 GO)
- **Static basis:** `docs/spike-adk2-supervisor-orchestration.md` (AH-96 CONDITIONAL GO)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §2 (Phase 0 de-risking scope), §8 (deploy smoke test plan), §9 (weave-autopatch carry-forward risk)
- **Probe scripts:** `docs/spike-adk2/probe-{8,9,10}-*.py`, `docs/spike-adk2/spike_deploy.py`, `docs/spike-adk2/cleanup_spike_engine.py`
- **Session service precedent:** `docs/spike-adk2/probe-5-session-service-schema.py` (AH-99 stored-event round-trip, extended by Probe 10 to live-deploy)
- **Sandbox pool contract:** `app/adk/agents/agent_factory/tests/test_sandbox_pool_runtime_rebuild.py`
- **Downstream:** [AH-105](https://linear.app/ken-e/issue/AH-105) (chat-tree pin bump — unblocked when §1 verdict flips to GO)
