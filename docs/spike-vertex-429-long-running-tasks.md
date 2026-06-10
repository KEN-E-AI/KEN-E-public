# Spike — Surviving Vertex AI 429s: long-running unattended agent tasks

**Date:** 2026-06-10
**Status:** Investigation complete — Tier 1 (O-1 retry + O-2 hygiene) selected and implemented in PR #970; Tier 2/3 options pending future telemetry
**Trigger:** Staging chat turn failed with `429 RESOURCE_EXHAUSTED` after ~13.7 minutes / 31 LLM calls. A competitor claims their agent runs "for hours without human intervention"; this spike quantifies why KEN-E currently cannot, and what it takes to get there.

---

## 1. Executive summary

A single transient Vertex throttle killed an entire 13.7-minute agent turn because **KEN-E performs zero retries on model calls**. The throttle was *not* a per-project quota we can raise — Cloud Monitoring shows **zero quota-exceeded events**; current Gemini models have **no per-project quota at all**. They run on shared capacity ("Usage Tiers" / Dynamic Shared Quota), where a 429 means momentary pool contention and Google's documented remedy is client-side exponential backoff.

The arithmetic is decisive. At the throttle rate observed in the incident window (~1 in 31 calls):

| Task length | Survival, no retry (today) | Survival, 5-attempt exponential backoff |
|---|---|---|
| This turn (31 calls) | 36% | >99.99% |
| 1 hour (~136 calls) | 1.2% | >99.99% |
| 2 hours (~272 calls) | 0.013% | >99.99% |
| 4 hours (~545 calls) | ~0% | >99.99% |

*(Idealized — assumes independent failures. Contention is time-correlated, so real-world retry effectiveness is lower than the right column, but the qualitative gap holds: retry converts near-certain failure into near-certain success.)*

**The competitor's "runs for hours" capability is not a quota story — it is a resilience story.** Average throughput in the incident was trivial (2.3 calls/min, ~36K input tokens/min) against a Tier-1 baseline of 2,000,000 tokens/min for Flash models. What we lack, in priority order: (a) **any retry** on 429/503 — the genai SDK ships full backoff machinery, opt-in, unused; (b) **traffic smoothing** — Google throttles on *second-level* spikes even when per-minute usage is far below the floor; (c) **checkpoint/resume** so a task that exhausts retries continues rather than dies. Paid escape valves exist if needed later (Priority PayGo: +80%/token, one header, no commitment; Provisioned Throughput: from $1,200/GSU-week).

One earlier hypothesis is **corrected** by this investigation: routing everything to the `global` endpoint (PR #968) did **not** shrink our capacity. Global is Google's *largest* pool and its documented best practice for avoiding 429s; regional/multi-region endpoints carry a +10% price premium and no baseline floor. Returning specialists to `us` is a **data-residency** play (the Review 51 revert), not a 429 remedy.

Compounding contributors confirmed: the GA specialist was switched to `gemini-3.5-flash` via MER-E (legitimate — it's GA since 2026-05-19 — but absent from KEN-E's own `SUPPORTED_MODELS`, which validates nothing at the ADK layer), the review loop re-ran the full multi-tool report flow (up to 3×/turn possible), and context caching is silently broken (mis-configured minimum), so every byte of the ~487K input tokens was sent uncached.

---

## 2. The incident — verified timeline

Staging, 2026-06-10, one user turn (W&B Weave trace `019eb170-9655-71b7-9f1c-b1ae658c74c9`, project `ken-e-staging`; Cloud Monitoring `serviceruntime.googleapis.com/api/request_count`; ReasoningEngine Cloud Logging):

| Time (UTC) | Event |
|---|---|
| ~12:01 | Turn starts. GA specialist (gemini-3.5-flash) begins multi-step report flow (GA MCP `get_account_summaries_mt`, `run_report_mt`, …). |
| 12:01–12:11 | 20 × `GenAiCacheService.CreateCachedContent` → **400** ("cached content is 2409 tokens; minimum is 4096"). Context caching never engages (see §7.2). |
| 12:06:26 | `mcp_pool.py:310` evict raises `AttributeError: 'McpToolset' object has no attribute 'aclose'` (caught; side bug, §7.3). |
| 12:07:10 | 1 × **503** on `StreamQueryReasoningEngine` (transient; turn continued). |
| 12:10:34 | 1 × **429** on `PredictionService.GenerateContent` (gemini-3.5-flash). No retry exists → exception propagates through `google_llm.py:272` → node runner → turn dies. User sees the raw error. |

Per-model usage in the turn (Weave):

| Model | Calls | Input tokens | Output tokens | Role |
|---|---|---|---|---|
| gemini-3.5-flash | 20 | ~445,953 | ~14,103 | GA specialist worker (review loop ran the full tool flow twice) |
| gemini-2.5-flash | 8 | ~14,348 | ~27,652 | review loop / numerical analyst |
| gemini-3.1-pro-preview | 3 | ~26,810 | ~522 | root coordinator |
| **Total** | **31** | **~487K** | **~42K** | over 819 s → 2.27 calls/min, ~36K input tok/min |

The single counted 429 at the API layer also proves empirically that **no SDK-level retry fired** (a retrying client would have produced multiple 429 counts).

---

## 3. Root cause — three layers

### 3.1 No retry anywhere (the fatal layer)

- ADK does **not** retry model calls. On 429 it re-raises (`google_llm.py:287-294`, ADK 2.0.0) — retry only happens if `Gemini.retry_options` is set, and KEN-E never sets it: every agent is built with a plain model *string* (`builder.py:488` `"model": config.model`), so `LLMRegistry.new_llm` creates a bare `Gemini` with `retry_options=None` on every call.
- Verified in the installed google-genai **1.75.0** source: `retry_args(None)` returns `stop_after_attempt(1)` — the "never retry" strategy (`_api_client.py:510-521`). Passing even an **empty** `HttpRetryOptions()` activates the full default policy: 5 attempts, exponential backoff 1 s → 60 s (base 2, jitter), retrying 408/429/500/502/503/504 and connect/timeout errors (`_api_client.py:491-543`). Known gap: the SDK does not honor the server's `retryDelay` hint ([googleapis/python-genai#1875](https://github.com/googleapis/python-genai/issues/1875)).
- Streaming coverage (verified in the same source): the tenacity wrapper surrounds request **initiation** for both `_request` and `_async_request` (`stream=` flag included), so a 429 at call setup is retried even for streaming calls; an error **mid-stream** (after first bytes) is not. KEN-E's LLM calls are non-streaming today — no `StreamingMode` is set anywhere in `app/adk`, so ADK defaults to `StreamingMode.NONE` and uses plain `generate_content` (`google_llm.py:272`, the exact call in the incident traceback) — so retry coverage is complete; revisit if token-level streaming is enabled.
- `ReflectAndRetryToolPlugin` (`deploy_ken_e.py:440`) covers **tool execution** errors only, never model-call errors.
- KEN-E's own `agent_retry.py:20-24` retries only `(ConnectionError, TimeoutError, OSError)` — a genai `ClientError` 429 is not in the set.
- Both deploy venvs (chat `.venv` google-adk 2.0.0 and strategy `.venv-adk1` google-adk 1.34.1) expose `Gemini.retry_options` — the fix applies to both trees.
- Google's [retry-strategy guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/retry-strategy) endorses exactly this for Standard PayGo, with one caveat for interactive chat: fail fast / limited attempts there, full backoff for background work.

### 3.2 Endpoint routing — hypothesis corrected

PR #968 sets `GOOGLE_CLOUD_LOCATION=global` process-wide (`model_routing.py` `apply_model_location_env()`; re-applied per turn at `sub_agent_attacher.py:657`). The genai client reads that env var at construction (`_api_client.py:663`) — it is the *only* location input; all models moved to `global` so the root (gemini-3.1-pro-preview, global-only) could be served.

**This did not reduce capacity.** Verified from current Google docs (all fetched 2026-06-10, pages stamped "Last updated 2026-06-09"):

- *"Using the global endpoint is a best practice, as it provides access to a larger, multi-region pool of throughput capacity"* ([Standard PayGo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/standard-paygo)); the [429 playbook](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/error-code-429) lists "use the global endpoint" as remedy #1.
- The Usage-Tier baseline TPM floor (§4) is defined **only** for global-endpoint traffic; Priority and Flex PayGo are **global-only**; non-global endpoints carry a **+10% token-price premium**.

So per-model routing back to `us` is justified **only by data residency** (shrinking the [Review 51](design/DESIGN-REVIEW-LOG.md) D4 exception to the one model that needs `global`) — and it remains feasible if wanted: `LlmAgent.model` accepts a `Gemini` **instance** (`llm_agent.py:208,554-561`), and ADK's own docstring (`google_llm.py:96-113`) documents the subclass-with-explicit-location pattern (pickle-safe; the `api_client` cached property populates lazily post-unpickle). Dead end ruled out: passing the model as a full resource path does **not** change the network endpoint — host derives from `client.location` only (`_api_client.py:744-768,1244-1255`).

The likely real 429 mechanics, per Google: *"If you receive a 429 error, it doesn't indicate that you've hit a fixed quota. It indicates temporary high contention for a specific shared resource"*, plus *"high and instantaneous traffic can lead to throttling even if your average per-minute usage is below your limit"* — our GA specialist fires bursts of sequential calls; second-level spikes throttle even at trivial per-minute volume.

### 3.3 Turn-cost amplification (the demand layer)

- **Model switch:** Firestore `agent_configs/google_analytics_specialist.model` = `gemini-3.5-flash` in **both staging and prod**, set 2026-06-10 10:11 UTC via MER-E. The seed pins `gemini-2.5-flash` (`migrate_ga_specialist_to_firestore.py:222`, AH-149). The switch is defensible — gemini-3.5-flash is **GA since 2026-05-19** ($1.50/M in, $9.00/M out on global) — but it exposed a governance gap: `gemini-3.5-flash` is absent from `SUPPORTED_MODELS` (`agent_config_models.py:29-49`), present in `context_windows.py:36` (the two mirrors disagree), and the ADK factory validates nothing (`config_loader.py` — `model: str`, no validator), so any string flows straight to Vertex.
- **Review loop:** the GA specialist has `default_acceptance_criteria`, so it is review-wrapped (`specialist_runtime.py:736`) with `max_iterations=3` (`review_pipeline.py:411`). The observed "ran the report flow twice" = a reviewer rejection causing the worker to redo its full multi-tool flow. Worst case is 3 full flows per turn.
- **Context accumulation:** MCP tool outputs (GA reports) are re-sent in full on every subsequent LLM call; only chart artifacts get summarized for the reviewer (`review_pipeline.py:249-314`). No token budget or per-turn circuit breaker exists.

---

## 4. Capacity truth — quotas, tiers, and what actually binds

**Per-project quotas (Cloud Quotas API, pulled 2026-06-10 for both `ken-e-staging` 391472102753 and `ken-e-production` 395770269870 — values identical):**

| Quota | Scope | Value |
|---|---|---|
| `GlobalGenerateContentInputTokensPerMinutePerBaseModel` — `gemini-3-pro` | global | 5,000,000 tokens/min |
| same — default (all unlisted base models) | global | **-1 (unlimited)** |
| Any per-project entry for `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.1-pro*` | any | **none — no per-project quota exists** |

Decisive cross-check: `serviceruntime.googleapis.com/quota/exceeded` shows **zero events across all services in the 36 h around the incident**, while `api/request_count` shows exactly one 429. **The 429 did not come from any per-project quota.** A quota-increase request is not a remedy — there is nothing to raise; Google's [quotas page](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/quotas) no longer lists RPM/TPM rows for Gemini text models at all.

**What governs instead — Usage Tiers** ([Standard PayGo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/standard-paygo)): the org's rolling 30-day spend on eligible SKUs sets a **baseline TPM floor per model family** on the global endpoint:

| Family | Tier 1 ($10–$250 / 30d) | Tier 2 ($250–$2,000) | Tier 3 (> $2,000) |
|---|---|---|---|
| Gemini Pro | 500K TPM | 1M TPM | 2M TPM |
| Gemini Flash / Flash-Lite | 2M TPM | 4M TPM | 10M TPM |

Bursting above baseline is best-effort; the only hard cap is a 30,000 RPM per-model-per-region system limit. **Preview models (gemini-3.1-pro-preview) get no floor at all** — pure shared pool. Our incident demand (~36K TPM) was ~2% of even the Tier-1 Flash floor: the binding constraint was **spike contention, not throughput** — which retry + pacing solves for free. *(Action: check the org's current tier on the Agent Platform Dashboard; crossing $250/30d doubles the Flash floor.)*

**Model lifecycle facts that matter to us** (model pages, all verified 2026-06-10):

- `gemini-2.0-flash` — **discontinued 2026-06-01**. This explains the dev-seed 404s previously attributed to dev-project entitlements. Any remaining 2.0-flash pins are dead in all environments.
- `gemini-2.5-flash` / `gemini-2.5-pro` — GA, but **retirement floor 2026-10-16**. A 2.5→3.x migration is needed this year regardless of this incident.
- `gemini-3.5-flash` — **GA 2026-05-19**; served on `global` **and** the `us`/`eu` multi-region endpoints (no single regions listed); supports PT, Priority, Flex, Batch.
- `gemini-3.1-pro-preview` — public preview (2026-02-19), **global-only**, no tier floor, but **is** PT-eligible and Priority/Flex-eligible.

---

## 5. What "runs for hours" actually requires

A representative long task at the incident's intensity: ~2.3 LLM calls/min and ~36K input tokens/min — i.e. ~136 calls and ~2.1M input tokens per hour. Capacity-wise this is trivial (2% of the Tier-1 Flash floor). The binding constraint is **compounded per-call failure probability** (§1 table): without retry, failure approaches certainty as call count grows; with backoff it approaches zero.

This matches how the ecosystem actually builds hours-long unattended agents:

1. **Retry transient errors** with exponential backoff + jitter at every model/tool call — table stakes on every provider.
2. **Durable execution / checkpoint-resume** — persist every step; on terminal failure resume from the checkpoint instead of restarting (LangGraph [durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution); the "LangGraph for reasoning, Temporal for durability" pattern). KEN-E already has the substrate: session events persist up to the failure point, and Project Tasks / `PlanRun` artifacts exist for multi-step work.
3. **Service tiers for capacity** — the industry converged on the same shape Google now has: Anthropic Priority Tier (committed capacity + overflow to standard), OpenAI `service_tier: priority` / Flex, AWS Bedrock Reserved/Priority/Flex. On Vertex the equivalents are Priority PayGo (+80%/token, global-only, one header — Google's doc names "agentic workflows" as the use case), Flex PayGo (−50%, Gemini 3.x only, latency-tolerant), and Provisioned Throughput (committed GSUs with default spillover to on-demand).
4. **Traffic smoothing** — client-side pacing/jitter between steps so bursts don't trip second-level throttles; alert at ~70–80% of sustained budget.

---

## 6. Options matrix

### Tier 1 — The resilience PR (one small PR + redeploy; days) — **the core fix**

| ID | Option | Effort | Impact | Cost | Residency |
|---|---|---|---|---|---|
| **O-1** | **Retry on 429/503** — implemented in PR #970 as a registry-level default (`ResilientGemini` registered over `gemini-*` in ADK's `LLMRegistry` from `apply_model_location_env()`), covering every string-model agent with zero construction-site changes. **Decision (Review 52): the policy is uniform across chat and task contexts** — Google's guidance suggests fail-fast for interactive chat, but worst-case added latency before a terminal failure is ~15s, accepted; per-context tuning is deferred until latency telemetry warrants it. | S | **Highest-leverage change in this report** — see §1 table | retried calls bill only on success | neutral |
| **O-2** | Hygiene riders: `ContextCacheConfig.min_tokens` 2048→4096 (§7.2); `mcp_pool.py` `aclose()`→`close()` (§7.3); add `gemini-3.5-flash` to `SUPPORTED_MODELS` + a model validator in the ADK config loader (§7.1) | XS | Stops 20 failed cache calls/turn; fixes MCP leak; closes the unvalidated-model gap | none | neutral |

### Tier 2 — Paid capacity valves (config/header-level; adopt if 429s persist post-O-1)

| ID | Option | Effort | Impact | Cost | Residency |
|---|---|---|---|---|---|
| **O-3** | **Priority PayGo** for heavy specialist/automation traffic: header `X-Vertex-AI-LLM-Shared-Request-Type: priority` via `HttpOptions(headers=…)` at the same builder change site (flag-gated) | XS–S | Premium processing pool; Google's named use case is "agentic workflows" | **+80% per token** on flagged traffic | global-only |
| **O-4** | **Flex PayGo** for latency-tolerant background runs (Automations/PlanRuns): same header mechanism, `flex` | S | Cheaper background execution; tolerate up to 30-min timeouts, don't retry aggressively | **−50% per token** | global-only; Gemini 3.x only |
| **O-5** | **Provisioned Throughput** for prod hot models (supports `global`, includes 3.5-flash and 3.1-pro-preview; default mode spills overage to on-demand — no 429s) | procurement | Guaranteed throughput | from **$1,200/GSU-week** (global; $2,700/GSU-month at 1-mo commit; −10–25% for 3/12-mo) | per-location purchase |

### Tier 3 — Structural (1–2 sprints each)

| ID | Option | Effort | Impact | Cost | Residency |
|---|---|---|---|---|---|
| **O-6** | Turn-efficiency: summarize/truncate MCP tool outputs in accumulated context; review-loop tuning (iteration cap per mode; AH-155 worker-instruction fix); pacing/jitter between agent steps (anti-spike) | M | Cuts per-turn calls/tokens ~2–3×; directly reduces contention exposure and cost | saves money | neutral |
| **O-7** | **Checkpoint/resume for long tasks**: on retry exhaustion persist turn progress (session events + plan artifacts already exist) and surface "resume" instead of a dead turn; "retrying…" status in chat | M–L | The durable competitive answer beyond retry — what "hours unattended" products actually do | none | neutral |
| **O-8** | AH-PRD-16 model-tier fallback (currently proposed, zero code): on sustained 429/404 after retries, fail over to next model in tier | M | Survives full-pool outages of a single model; also the answer to the 2.5-family retirement | none | neutral |
| **O-9** | Per-model location routing (`Gemini` subclass w/ explicit location): root stays `global`, others → `us`/`eu` | S–M | **Residency only** (shrinks the D4/Review 51 exception) — *not* a 429 remedy; non-global adds +10% token price | +10% on rerouted traffic | **improves** |

---

## 7. Side findings (file separately)

1. **Catalogue drift / no validation:** `gemini-3.5-flash` is live in prod+staging configs yet absent from `SUPPORTED_MODELS` (`api/src/kene_api/models/agent_config_models.py`) while present in `context_windows.py:36`; the ADK factory accepts any model string from Firestore unvalidated. MER-E can set anything. (Related: `mer-e-tool-catalogue-static-mirror-drift`.)
2. **Cache misconfig:** `deploy_ken_e.py:443` `min_tokens=2048` is below Gemini's server-side minimum of 4096 → every CreateCachedContent attempt 400s (20×/turn, zero caching). Working caching also cuts cost ~10× on repeated context and burns at 0.1× against PT GSUs.
3. **MCP pool bug:** `mcp_pool.py:310` calls `toolset.aclose()`; ADK 2.0's `McpToolset` only has `close()` — evicted toolsets are never closed (connection leak; exception caught).
4. **Model EOL exposure:** `gemini-2.0-flash` discontinued 2026-06-01 (explains the dev seed 404s memory); `gemini-2.5-flash`/`-pro` retire not-before 2026-10-16 — the reviewer default (`gemini-2.5-pro`, `review_pipeline.py:44`) and compaction summarizer (`deploy_ken_e.py:428`, `gemini-2.5-flash`) need a migration plan. O-8 (tier fallback) is the systemic answer.
5. **Strategy tree parity:** any `builder.py`/`model_routing.py` change rides into both deploy trees (chat ADK 2.0.0 and strategy supervisor ADK 1.34.1); `retry_options` is supported in both, but test both packagings (see memory `agent-engine-two-deploy-trees`).
6. **Agent Engine has its own quotas** (separate from model serving): e.g. `StreamQuery` 90/min per project per region — not near binding today, but relevant to many-concurrent-automations futures.

## 8. Recommended sequence

1. **O-1 + O-2 now, as one PR** — retry is the entire ballgame for unattended reliability; hygiene riders share the change site. Acceptance: re-run the staging GA turn; verify in Weave that any 429 is absorbed by backoff.
2. **O-6 next sprint** (biggest cost/contention lever), then **O-7** (checkpoint/resume) as the durable competitive answer; **O-8** opportunistically alongside the 2.5-family EOL migration.
3. **O-3/O-4 (Priority/Flex)** only if post-O-1 telemetry still shows retry exhaustion; **O-5 (PT)** only with sustained prod load to justify commitment.
4. **O-9** rides with the already-documented EU in-geography revert when EU go-live approaches — not before.

## 9. References

- W&B Weave trace `019eb170-9655-71b7-9f1c-b1ae658c74c9` (`ken-e/ken-e-staging`)
- [Data Residency Architecture §3.5](design/data-residency-architecture.md) — interim `global` exception + revert trigger; [DESIGN-REVIEW-LOG Reviews 50–51](design/DESIGN-REVIEW-LOG.md)
- [AH-PRD-16 Model Tier Registry](design/components/agentic-harness/projects/AH-PRD-16-model-tier-registry.md) (proposed)
- `app/adk/agents/agent_factory/model_routing.py`, `builder.py`, `specialist_runtime.py`, `app/adk/deploy_ken_e.py`
- Google docs (fetched 2026-06-10; product re-branding to "Gemini Enterprise Agent Platform" in progress): [Standard PayGo / Usage Tiers](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/standard-paygo) · [Consumption options](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deploy/consumption-options) · [429 playbook](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/error-code-429) · [Retry strategy](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/retry-strategy) · [Priority PayGo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/priority-paygo) · [Flex PayGo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/flex-paygo) · [Provisioned Throughput](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/provisioned-throughput) · [Quotas](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/quotas) · [Reduce 429 errors (blog)](https://cloud.google.com/blog/products/ai-machine-learning/reduce-429-errors-on-vertex-ai)
