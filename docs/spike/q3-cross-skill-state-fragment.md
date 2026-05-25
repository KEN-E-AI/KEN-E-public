# SK-4 Q3 — Cross-skill state contamination

> [!NOTE]
> **Same-session capture complete (2026-05-25).** Wave 2.5 harness rework
> (SK-33) shipped a trustworthy direct-mode harness; this fragment was
> re-run from a credentialled workstation against the live spike Agent
> Engine. **Inferred all-LEAK prediction confirmed: 5/5 vectors LEAK
> same-session.** Per-vector table rows are now `LEAK` (live capture), not
> `INFERRED: LEAK`. The "Implication for Skills" section's load-bearing
> claim (`SandboxPool` `(account_id, config_id)` keying is the right
> isolation boundary; per-skill isolation would require per-skill executors)
> is empirically validated.
>
> Cross-session results remain from the standalone host-process test (does
> not depend on the harness, so was unaffected by the regression).

> **Fragment status:** Cross-session results CONFIRMED via standalone OS-process isolation test (no GCP required).
> Same-session results INFERRED from ADK documentation ("state persists within a session" guarantee).
> PO empirical confirmation pending for same-session (requires `ken-e-api@ken-e-dev.iam.gserviceaccount.com`
> with `roles/aiplatform.user` on `ken-e-dev` — same credentials used for SK-1 AC#4).
>
> Raw logs: `docs/spike/q3-raw/` (same-session/cross-session harness invocations
> captured on the Dev Team VM; harness exited early because
> `KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME` was unset — see the **Failure attribution**
> note in the `### Result` section).

---

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

Security Severity: medium

SK-8 follow-up: Record the all-LEAK same-session finding under "Cross-skill state contamination"
in the go/scoped-go/no-go recommendation. Note that the `SandboxPool` (account_id, config_id)
keying is the correct isolation boundary; no design change required. Add authoring UI warning
to the scoped-go conditions. Mark as "pending empirical confirmation" until the sandbox run
completes.

SK-9 escalation: No immediate escalation required (medium severity, not high/critical). The
sandbox is an explicit opt-in (`sandbox_code_executor_enabled=true`) and requires an admin-level
agent config change; the attack surface is limited to accounts that have already opted in. If
empirical results show a cross-account leak (not expected given `SandboxPool` keying), escalate
to `security@ken-e.ai` immediately and raise severity to critical.
