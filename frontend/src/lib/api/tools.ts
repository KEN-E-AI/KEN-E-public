import api from "@/lib/api";

// ─── Account tool inventory (AH-PRD-06 §4) ───────────────────────────────────
//
// Mirrors ``AccountToolEntry`` / ``AccountToolsResponse`` in
// ``api/src/kene_api/models/tool_models.py``. The backend composes the
// inventory from the static catalogue (``tools.yaml``) plus the account's
// connected integrations, so what the picker shows and what the agent-config
// API accepts stay in sync.

export type AccountToolSource = "global_default" | "integration";

export type AccountToolEntry = {
  /** Canonical ID — ``<mcp_server>.<tool_name>`` or ``function.<tool_name>``. */
  tool_id: string;
  name: string;
  description: string;
  category: string;
  source: AccountToolSource;
  /** Set for integration tools, null for built-in function tools. */
  mcp_server: string | null;
  /** Set for integration tools, null for built-in function tools. */
  integration_platform: string | null;
};

export type AccountToolsResponse = {
  tools: AccountToolEntry[];
};

// ─── API client ───────────────────────────────────────────────────────────────

export async function getAccountTools(
  accountId: string,
): Promise<AccountToolsResponse> {
  const { data } = await api.get<AccountToolsResponse>(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/tools`,
  );
  return data;
}
