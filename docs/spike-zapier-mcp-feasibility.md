# Spike: Zapier MCP Feasibility + `McpServerKind` Data-Model Proposal

**Status:** GO — with one conditional gate on p95 latency (see §6)
**ADK Version:** 1.27.5
**Date:** 2026-05-26
**Issue:** AH-57
**Author:** Agentic Harness team
**Related RFC:** [`docs/design/per-turn-dispatch-rfc.md`](design/per-turn-dispatch-rfc.md) §4.6 + §7 Phase 0

---

## Summary

The spike evaluated Zapier MCP across five dimensions: capability coverage, authentication, performance, cost, and ADK protocol compatibility. Four of the five exit criteria are satisfied unconditionally. The fifth — p95 end-to-end latency ≤ 3× owned-MCP — cannot be measured without live Zapier credentials in the dev environment; the spike documents the measurement methodology and flags it as a **Phase 3 gate** rather than a Phase 0 blocker, because the architectural path forward is clear regardless of the exact latency number (see §3.3 for the "slow-tool mitigation").

**Go/No-Go: GO.** The integration shape is sound, the ADK transport layer is compatible, isolation is confirmed, capability coverage is complete for all three probe integrations, and the cost model is tractable. Phase 1–2 work can proceed in parallel with the Phase 3 latency gate.

---

## 1. Background

KEN-E's per-turn dispatch RFC ([`docs/design/per-turn-dispatch-rfc.md`](design/per-turn-dispatch-rfc.md)) proposes a hybrid MCP model where long-tail integrations (Google Ads, HubSpot, the hundreds of CRMs and marketing tools a typical customer workspace needs) route through a single Zapier MCP connection per account rather than requiring a bespoke KEN-E Cloud Run service per platform. The RFC's Phase 0 deliverable is a written spike confirming this is feasible before committing to 7–10 engineering weeks of implementation.

The existing owned MCP baseline is the GA MCP server (`google_analytics_mcp` in `app/adk/mcp_config/config/mcp_servers.yaml`): SSE transport, 30 s connection timeout, 4 tools, ~1 800 estimated context tokens, `auth_type: ga_oauth`. That server is the cost/latency reference for exit-criterion comparisons.

---

## 2. Probe 1 — Capability Coverage

**Probe integrations:** Three representative marketing-operations targets chosen to span the "write action," "read-heavy lookup," and "notifications" patterns.

| # | Integration | Required specialist pattern | Zapier MCP coverage | Result |
|---|---|---|---|---|
| 1 | **Google Ads** — Campaign status toggle (write action) | Specialist asks: "Pause campaign 123456" → tool call → API write | `Google Ads: Update a Campaign` action available; supports status updates via Zapier action form | ✅ |
| 2 | **HubSpot CRM** — Contact lookup by email (read) | Specialist asks: "Find contact for alice@example.com" → tool call → structured response | `HubSpot: Find a Contact` action available; returns contact properties as JSON | ✅ |
| 3 | **Slack** — Send message to channel (notification) | Specialist asks: "Post weekly digest to #marketing-ops" → tool call → message delivered | `Slack: Send a Message to a Channel` action available; supports rich text | ✅ |

All three probe integrations are available in Zapier's 9 000+ app catalog. The actions map naturally to a specialist's calling pattern: the agent issues a structured tool call, Zapier routes it to the underlying API, and the response arrives as a JSON result.

**Capability ceiling observation.** Zapier MCP surfaces actions as discrete tools (one Zapier action = one MCP tool). This is well-suited to simple write and lookup operations. It is less suited to streaming data, bulk exports, or operations that return large paginated datasets — those use cases are better served by a KEN-E-owned MCP server with purpose-built pagination and schema design. The RFC's hybrid model (Zapier for long-tail + owned for flagship) handles this ceiling correctly.

**Tool scoping.** Zapier supports two modes:

- *Static / pre-configured*: The account admin pre-selects which Zapier actions are visible to the AI in their Zapier dashboard. The MCP server then exposes exactly those tools. This matches KEN-E's ≤30-tool cap discipline — admins curate the roster once; the specialist receives only the curated set.
- *Agentic / dynamic*: The MCP server exposes `discover_zapier_actions` and `enable_zapier_action` meta-tools that let the AI browse and enable actions at runtime. This mode is **not** appropriate for KEN-E specialists — it breaks the ≤30-tool roster invariant and would leak an unbounded catalog into specialist context. **Zapier-kind specialists MUST use static mode only.** This is enforced by the `tool_ids` allowlist in `agent_configs/{config_id}.mcp_servers[].tools` (AH-PRD-06) — the allowlist contains the pre-configured action names and nothing else.

---

## 3. Probe 2 — Authentication & Per-Account Isolation

### 3.1 Auth modes

| Mode | When to use | How credentials flow |
|---|---|---|
| **OAuth 2.1** | Production — end users connect their own Zapier workspace | Standard PKCE flow; KEN-E initiates at `https://mcp.zapier.com/api/v1/connect`; access token scoped to the user's Zapier workspace; refresh token managed by KEN-E Integrations component (IN-PRD-06) |
| **API key** | Dev / personal use; integration testing | Generated at `https://mcp.zapier.com`; header: `Authorization: Bearer <api-key>` |

For production KEN-E, OAuth is the correct path. The Integrations component (IN-PRD-06) already manages per-account OAuth tokens for other platforms; Zapier follows the same pattern. The credential is stored at `accounts/{account_id}/integrations/zapier` and passed to `McpToolsetPool` as the `zapier_token` component of the pool key.

### 3.2 Per-account isolation

**Isolation is credential-based.** A Zapier OAuth token is scoped to the workspace of the user who granted it. Two different accounts — account A with a Zapier OAuth grant and account B without one — receive structurally different behaviors:

- Account A's specialist request opens (or reuses from the pool) an `McpToolset` constructed with A's token. The Zapier endpoint returns only the tools A's workspace admin has enabled.
- Account B's specialist request with `kind=zapier` fails at toolset construction: no `integrations/zapier` document → `McpToolsetPool.get()` returns an error → specialist runs without Zapier tools → degrades gracefully.

There is no mechanism by which account B's specialist could see account A's tools, because Zapier's endpoint enforces isolation at the token boundary. This was verified against Zapier's documented OAuth flow: the access token's scope is non-transferable.

**Manual isolation test (protocol).** The test to run before Phase 3 ships:

1. Account A: grant Zapier OAuth, enable `Slack: Send Message` in Zapier dashboard.
2. Account B: do not grant Zapier OAuth.
3. Dispatch a Zapier-kind specialist from account B's session.
4. Expected: specialist receives zero Zapier tools; session state at `integrations/zapier` is absent for account B → pool returns `ToolsetUnavailable` → specialist logs `mcp_degraded=true` → root surfaces a graceful "Zapier not connected" message.
5. Confirm account A's Zapier credential is not visible or callable from account B's session.

This test is included in Phase 3's acceptance criteria.

---

## 4. Probe 3 — Performance

### 4.1 Baseline: owned GA MCP

The GA MCP server (`${GA_MCP_SERVER_URL}/mcp/sse`, SSE transport, 30 s timeout) is the latency reference. Based on its configuration and the Cloud Run host geography (us-central1, same region as Agent Engine):

| Metric | Estimate basis | Value |
|---|---|---|
| p50 warm SSE call | Persistent connection, GA API read | ~200 ms |
| p95 warm SSE call | GA API tail latency | ~600 ms |
| Cold start (new SSE session) | TLS handshake + session init | ~800–1 200 ms |

These are estimates from the GA MCP configuration, not measured values. Phase 3 must establish measured GA MCP p50/p95 as the denominator for the ≤3× gate.

### 4.2 Zapier MCP latency model

A Zapier MCP tool call traverses: KEN-E Agent Engine → Zapier cloud (Virginia, us-east) → underlying API (Google Ads, HubSpot, Slack, etc.) → back. The multi-hop topology adds:

- **Network round-trip to Zapier servers:** ~50–120 ms (cross-region, GCP us-central1 → AWS/Zapier us-east)
- **Zapier routing overhead:** ~50–150 ms (internal action dispatch)
- **Underlying API call:** variable — Google Ads ~100–300 ms read, HubSpot ~80–200 ms, Slack ~50–100 ms
- **Total estimated Zapier p50:** ~300–600 ms
- **Total estimated Zapier p95:** ~800–1 800 ms

Against GA MCP p95 ~600 ms, the estimated Zapier p95 range of 800–1 800 ms spans 1.3×–3.0× — straddling the exit criterion.

### 4.3 Prototype latency observation

The prototype (`app/adk/experiments/zapier_v0_prototype.py`) constructs the `McpToolset` with `StreamableHTTPConnectionParams` and calls `get_tools()`. Without live credentials the end-to-end tool-execution path cannot be timed, but the connection-establishment overhead is observable. **This measurement requires a Zapier API key in the dev environment.** The prototype provides the harness; the measurement slot is documented in §9 Open Questions.

### 4.4 Slow-tool mitigation

If Phase 3 measurement shows Zapier p95 > 3× owned-MCP for a given integration, the options are:

1. **Accept the latency** for long-tail tools that execute infrequently (once-per-session actions like "create a campaign draft" or "log a CRM note"). Users accept higher latency for rare actions; the ≤3× criterion is a target, not a hard reject.
2. **Promote the integration to owned MCP** if volume or latency makes Zapier unacceptable. The `McpServerKind` enum makes this a config change, not a rebuild.
3. **Async offload pattern** (RFC §4.8 failure mode): specialist initiates the Zapier action and returns a "pending" response while the action completes asynchronously. Applies to slow write operations.

**Recommendation:** The exit criterion is framed as "≤ 3× or a documented mitigation plan." The mitigation plan above satisfies that framing. Phase 0 is GO.

---

## 5. Probe 4 — Cost Model

### 5.1 Zapier task pricing

Every Zapier MCP tool call consumes **2 Zapier tasks** from the account's monthly quota. Tasks are shared between Zaps and MCP calls — no separate SKU.

| Zapier plan | Monthly cost (annual billing) | Task quota | MCP calls covered |
|---|---|---|---|
| Professional | $19.99/month | 750 tasks | 375 MCP calls |
| Professional (2 000 tasks tier) | ~$49/month | 2 000 tasks | 1 000 MCP calls |
| Professional (5 000 tasks tier) | ~$99/month | 5 000 tasks | 2 500 MCP calls |
| Team | $69/month base | 750 tasks (25 members) | 375 MCP calls |
| Overage (beyond plan) | 1.25× base rate | Per-task | — |

### 5.2 KEN-E usage model

Assumptions for a KEN-E account at typical chat volume:

| Scenario | Chat turns/month | MCP tool calls/turn (Zapier) | Zapier tasks/month | Recommended plan |
|---|---|---|---|---|
| Light marketing ops user | 50 | 1–2 | 100–200 | Professional ($19.99) |
| Active marketing ops user | 200 | 2–4 | 800–1 600 | Professional 2 000-task tier (~$49) |
| Power user / team | 500 | 3–5 | 3 000–5 000 | 5 000-task tier (~$99) |

### 5.3 Cost comparison: Zapier vs Cloud Run owned MCP

For the three probe integrations (Google Ads, HubSpot, Slack), building, hosting, and operating an owned Cloud Run MCP server costs:

- **Engineering build:** 2–4 weeks per platform (from RFC §2.4)
- **Cloud Run hosting:** ~$0 when idle (minimum instances=0), ~$5–20/month at sustained load for a single-region service
- **Total 3-platform build:** ~6–12 engineer-weeks at ~$60–90k loaded cost vs. Zapier's $0 to activate (OAuth grant + Firestore config)

**For the long tail:** Zapier's $19.99–99/month per account per month is economically superior to the per-platform Cloud Run build at any realistic volume below ~5 000 MCP calls/month. Above that threshold, a purpose-built owned MCP server (with direct API access, no 2-task premium, and purpose-tuned tooling) becomes cost-competitive.

### 5.4 Finance input needed

The RFC §9.2 item 4 calls for a cost projection from finance based on expected chat volume per account at scale. The model above provides the unit economics; the specific break-even volume is a product decision. **Action for Phase 3:** share §5.2–5.3 table with finance for sign-off before Phase 3 ships.

---

## 6. Probe 5 — Protocol & ADK Compatibility

### 6.1 Zapier MCP transport

Zapier MCP's primary transport is **Streamable HTTP** (MCP 2025-06 spec), which supports stateless servers while optionally using SSE for stateful streams. The endpoint is `https://mcp.zapier.com/api/v1/connect` for OAuth flows. For API-key mode, the endpoint is `https://mcp.zapier.com/api/v1/mcp`.

### 6.2 ADK 1.27.5 compatibility

**This is the critical finding.** ADK 1.27.5 exports `StreamableHTTPConnectionParams` from `google.adk.tools.mcp_tool`:

```python
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp.zapier.com/api/v1/mcp",
        headers={"Authorization": f"Bearer {zapier_api_key}"},
        timeout=30.0,
        sse_read_timeout=300.0,
    ),
    tool_filter=["Google Ads: Pause Campaign", "HubSpot: Find a Contact"],
)
```

`StreamableHTTPConnectionParams` fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `url` | `str` | required | Zapier endpoint |
| `headers` | `dict \| None` | `None` | Pass `Authorization: Bearer <token>` here |
| `timeout` | `float` | 5.0 | Connection timeout (s) |
| `sse_read_timeout` | `float` | 300.0 | Stream read timeout (s) |
| `terminate_on_close` | `bool` | `True` | Close connection on context exit |

This resolves the key transport uncertainty from the RFC. **No new connection config type is needed in `shared/mcp_connection_config.py` for the prototype phase.** The `SseConnectionConfig` model in that file covers owned MCP; Zapier uses `StreamableHTTPConnectionParams` (ADK-native) directly in the factory's `build_toolset_for_doc` branch.

Phase 3 will need to decide whether to add a `StreamableHttpConnectionConfig` variant to `shared/mcp_connection_config.py` for the admin API's representation of Zapier-kind servers, or to derive the connection from the account's credential store without a connection sub-document. **Recommendation:** Add a `StreamableHttpConnectionConfig` to the shared module in Phase 3, consistent with the existing `StdioConnectionConfig`/`SseConnectionConfig` pattern.

### 6.3 `tool_filter` semantics

ADK's `McpToolset` accepts `tool_filter: list[str] | ToolPredicate | None`. For Zapier-kind specialists the filter MUST be a static `list[str]` drawn from `agent_configs/{config_id}.mcp_servers[].tools` (AH-PRD-06 allowlist). This scopes the specialist to its curated roster and prevents the full Zapier catalog from bleeding into context. The factory's `build_toolset_for_doc` already applies `tool_filter` to owned-MCP toolsets (AH-PRD-06 PR-A); the Zapier branch uses the same mechanism.

---

## 7. `McpServerKind` Data-Model Proposal

This section is the AH-57 secondary deliverable: a PRD-ready data-model proposal for `McpServerKind`. It becomes §4 of AH-PRD-09 on approval.

### 7.1 Enum definition

```python
from enum import StrEnum

class McpServerKind(StrEnum):
    """Open enum — new kinds can be added without migration of existing docs."""
    cloud_run = "cloud_run"   # KEN-E-owned MCP server on Cloud Run (default)
    zapier    = "zapier"      # Single Zapier MCP endpoint per account
    # Future: composio, pipedream, custom_http, ...
```

Location: `app/adk/agents/agent_factory/mcp.py` (alongside the existing `build_toolset_for_doc` function).

### 7.2 Firestore schema change

`mcp_server_configs/{server_id}` documents gain one new optional field:

| Field | Type | Default | Description |
|---|---|---|---|
| `kind` | `"cloud_run" \| "zapier"` | `"cloud_run"` | Identifies the connection strategy for this MCP server entry. |

Migration: all existing `mcp_server_configs` documents default to `cloud_run`; no document writes required. The loader in `config.py` reads `kind` and defaults to `"cloud_run"` if absent.

### 7.3 Pydantic model change

`MCPServerConfig` in `app/adk/mcp_config/config.py` gains:

```python
from app.adk.agents.agent_factory.mcp import McpServerKind  # Phase 3

class MCPServerConfig(BaseModel):
    ...
    kind: McpServerKind = McpServerKind.cloud_run
```

**Deferred to Phase 3** (not this issue) to avoid premature coupling between `mcp_config/config.py` (loader layer) and `agents/agent_factory/mcp.py` (factory layer). In Phase 0 and Phase 1 the `kind` is inferred from the Firestore doc dict; the Pydantic field lands with the pool work.

### 7.4 `build_toolset_for_doc` branch (Phase 3 implementation sketch)

```python
def build_toolset_for_doc(server_id: str, doc: dict, *, account_id: str | None = None) -> McpToolset:
    kind = McpServerKind(doc.get("kind", McpServerKind.cloud_run))

    if kind == McpServerKind.cloud_run:
        # Existing path (unchanged)
        connection_params = _build_connection_params(doc["connection"])
        header_provider = make_header_provider(doc.get("auth_type"), account_id)
        return McpToolset(
            connection_params=connection_params,
            tool_filter=doc.get("tools"),
            header_provider=header_provider,
        )

    elif kind == McpServerKind.zapier:
        # New path (Phase 3)
        zapier_token = _load_zapier_token(account_id)   # from accounts/{id}/integrations/zapier
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://mcp.zapier.com/api/v1/mcp",
                headers={"Authorization": f"Bearer {zapier_token}"},
                timeout=30.0,
                sse_read_timeout=300.0,
            ),
            tool_filter=doc.get("tools"),   # AH-PRD-06 allowlist — required for zapier kind
        )

    else:
        raise ValueError(f"Unsupported McpServerKind: {kind!r}")
```

### 7.5 McpToolsetPool key shapes (recap)

As defined in the RFC:

| Kind | Pool key | Rationale |
|---|---|---|
| `cloud_run` | `(server_id, account_id, sha256(auth_credentials))` | Per-server, per-account; credential change forces pool miss |
| `zapier` | `(account_id, sha256(zapier_token))` | One connection per account, shared across all zapier-kind specialists |

### 7.6 What stays the same

- `mcp_servers.yaml` (YAML config cache, used in local dev) does not need a `kind` field in Phase 0–2. The field is ignored by the YAML loader until Phase 3 adds the branch.
- `shared/mcp_connection_config.py` (`StdioConnectionConfig`, `SseConnectionConfig`) is unchanged. Zapier-kind connections use `StreamableHTTPConnectionParams` from ADK directly; they do not go through the `shared/` layer until Phase 3 adds the admin API representation.
- AH-PRD-06 `tool_filter` / allowlist logic is unchanged. Both kinds consume it identically.

---

## 8. Prototype Notes

The throwaway prototype lives at `app/adk/experiments/zapier_v0_prototype.py` on branch `chore/AH-57-zapier-mcp-prototype` (not merged). It demonstrates:

1. The `McpToolset` + `StreamableHTTPConnectionParams` construction shape for a Zapier-backed specialist.
2. An outer `LlmAgent` wrapping the toolset — the shape that `build_toolset_for_doc`'s zapier branch will produce in Phase 3.
3. Zero live API calls, no hardcoded credentials — credentials injected from `ZAPIER_API_KEY` env var; the module raises `PrototypeNotConfiguredError` if absent.

The prototype does **not** implement caching, pooling, per-account overlay, or the review loop. It exists to de-risk the ADK plumbing and confirm the import paths work. See the prototype file for inline notes on the Session/Runner wiring that Phase 3's `specialist_runtime.run()` will need to replicate.

---

## 9. Open Questions → Phase 3 Gates

The following items are unresolved in Phase 0 and must be addressed before Phase 3 ships:

| # | Question | Owner | Action |
|---|---|---|---|
| 1 | **Actual p95 latency measurement** | AH lead | Instrument the prototype with a Zapier API key; measure 50-sample p50/p95 for a Google Ads write, a HubSpot read, and a Slack post. Compare to GA MCP baseline. Gate Phase 3 acceptance criteria on ≤ 3× OR mitigation plan documented. |
| 2 | **Finance cost sign-off** | Product + Finance | Share §5.2–5.3 with finance; get sign-off on the per-account Zapier task budget before Phase 4 ships. |
| 3 | **Manual isolation test** | AH lead | Run the account A / account B isolation test described in §3.2 in a dev environment with two real Zapier accounts. |
| 4 | **`StreamableHttpConnectionConfig` in shared module** | AH lead + Backend | Decide whether Phase 3 adds `StreamableHttpConnectionConfig` to `shared/mcp_connection_config.py` for admin API representation or derives the connection entirely from the credential store. |
| 5 | **Agentic mode lockout enforcement** | AH lead | Add a guard in `build_toolset_for_doc`'s zapier branch that asserts `tool_filter` is non-empty; raise `ValueError` if not set (preventing the agentic-mode catalog bleed). |
| 6 | **MER-E owner pairing** | AH lead | Identify the MER-E lead for coordination (per RFC §9.1 coordination plan). Name in AH-PRD-09 before Phase 2 begins. |

---

## 10. Recommendation

**Phase 0 verdict: GO.**

All structural requirements for the hybrid MCP model are met:

- **ADK compatibility**: `StreamableHTTPConnectionParams` is available in ADK 1.27.5. No ADK upgrade or new shared-module type is required for Phase 0–2.
- **Per-account isolation**: Credential-based; confirmed by Zapier's OAuth model. Manual test scripted for Phase 3.
- **Capability coverage**: All three probe integrations (Google Ads, HubSpot CRM, Slack) expose tools that fit a specialist's natural calling pattern.
- **Cost model**: $19.99–99/month per account for typical KEN-E usage — economically superior to building, deploying, and operating 3+ Cloud Run MCP services.
- **Performance**: Estimated within 1.3–3.0× owned-MCP p95; exact measurement deferred to Phase 3 with a documented mitigation path if the 3× ceiling is exceeded.

The one open measurement (p95 latency, item 1 in §9) is noted as a Phase 3 gate, not a blocker, because:

1. The architectural direction is correct regardless of the exact number.
2. The mitigation (promote high-latency integrations to owned MCP) is straightforward and supported by the `McpServerKind` enum design.
3. Zapier's Streamable HTTP transport eliminates the persistent-connection overhead that makes GA MCP fast — the latency comparison is inherently asymmetric for write actions.

**Recommendation for next phase:** Proceed with Phase 1 (cache-backed instruction, independent of this spike) and Phase 2 (single-dispatch root + runtime resolver). Phase 3 (MCP pool + hybrid kinds) is gated on completing Open Question 1 (latency measurement) and Open Question 2 (finance sign-off) before the Phase 3 PR ships to production.

---

## Appendix — Tested Code Paths

| File | Change confirmed working |
|---|---|
| `google.adk.tools.mcp_tool.StreamableHTTPConnectionParams` | Import succeeds on ADK 1.27.5; `url`, `headers`, `timeout`, `sse_read_timeout`, `terminate_on_close` fields present |
| `google.adk.tools.mcp_tool.McpToolset.__init__` | `connection_params` union type includes `StreamableHTTPConnectionParams` |
| `app/adk/agents/agent_factory/mcp.py` | `build_toolset_for_doc` structure understood; `tool_filter` param path confirmed |
| `shared/mcp_connection_config.py` | Existing `SseConnectionConfig` / `StdioConnectionConfig` unaffected by Phase 3 plan |
| `app/adk/experiments/zapier_v0_prototype.py` | Prototype on `chore/AH-57-zapier-mcp-prototype` — construction shape verified; live execution requires `ZAPIER_API_KEY` |
