import type { Brand } from "@/lib/branded-types";
import api from "@/lib/api";

// ─── Branded type ────────────────────────────────────────────────────────────

export type AgentConfigId = Brand<string, "AgentConfigId">;

export const isAgentConfigId = (value: string): value is AgentConfigId =>
  value.length > 0;

export const toAgentConfigId = (value: string): AgentConfigId => {
  if (!isAgentConfigId(value)) {
    throw new Error(`Invalid AgentConfigId: ${value}`);
  }
  return value as AgentConfigId;
};

export const tryAgentConfigId = (value: string): AgentConfigId | undefined =>
  isAgentConfigId(value) ? (value as AgentConfigId) : undefined;

// ─── Model constants (mirrors SUPPORTED_MODELS in agent_config_models.py) ────

export const SUPPORTED_MODELS = [
  "gemini-3-flash-preview",
  "gemini-3-pro-preview",
  "gemini-2.5-flash",
  "gemini-2.5-pro",
  "gemini-1.5-pro",
  "gemini-1.5-flash",
  "gpt-4o",
  "gpt-4o-2024-08-06",
  "gpt-4o-mini",
  "o1-preview",
  "o1-mini",
] as const;

export type SupportedModel = (typeof SUPPORTED_MODELS)[number];

// ─── TypeScript types (mirrors agent_config_models.py:MergedAgentConfig) ─────

export type CustomizationStatus = "default" | "customized" | "custom_agent";

export type MergedAgentConfig = {
  config_id: string;
  // Human name (e.g. "Dave"). Optional, user-editable.
  name: string | null;
  // Role description (e.g. "Business Researcher"). User-editable.
  title: string | null;
  instruction: string;
  model: string;
  description: string | null;
  temperature: number | null;
  code_execution_enabled: boolean;
  mcp_servers: string[];
  skill_ids: string[];
  // Per-agent tool allowlist (AH-PRD-06). Semantics:
  //   null  → legacy "all tools from attached servers" (pre-PRD agents)
  //   []    → explicit "no tools"
  //   [...] → exactly these tools
  tool_ids: string[] | null;
  sandbox_code_executor_enabled: boolean;
  response_schema: Record<string, unknown> | null;
  available_to_copy: boolean;
  automatically_available: boolean;
  visible_in_frontend: boolean;
  // AH-82: whether KEN-E may delegate tasks to this agent from chat.
  ken_e_sub_agent: boolean;
  customization_status: CustomizationStatus;
  based_on_version: number | null;
};

export type AgentConfigCreate = {
  title: string;
  name?: string | null;
  instruction: string;
  model: string;
  description?: string | null;
  temperature?: number | null;
  skill_ids?: string[];
  // AH-PRD-06: omit for legacy "all tools" behaviour; [] for no tools; an
  // explicit list for an allowlist. The API caps at 30 entries.
  tool_ids?: string[] | null;
  sandbox_code_executor_enabled?: boolean;
  // AH-82: whether KEN-E may delegate tasks to this agent from chat.
  ken_e_sub_agent?: boolean;
};

export type AgentConfigOverlayUpdate = {
  name?: string | null;
  title?: string | null;
  instruction?: string | null;
  model?: string | null;
  description?: string | null;
  temperature?: number | null;
  skill_ids?: string[] | null;
  tool_ids?: string[] | null;
  sandbox_code_executor_enabled?: boolean | null;
  // AH-82: overlay value for the delegation gate. null = leave existing
  // overlay value untouched; explicit true/false = write the value.
  ken_e_sub_agent?: boolean | null;
};

// ─── Display helpers ──────────────────────────────────────────────────────────

export type AgentDisplay = {
  /** Primary line (bold, top). Falls back to title, then Title-Cased config_id. */
  primary: string;
  /** Secondary line (bold, beneath). Only set when name + title are both present
   *  and the secondary value adds information beyond the primary line. */
  subtitle: string | null;
};

/**
 * Resolve how an agent should be rendered in any UI surface (list cards,
 * edit-sheet headers, chat references, etc.).
 *
 * Display chain:
 *   1. `config.name` (human name like "Dave") → primary; if title is also
 *      set, title appears as the subtitle.
 *   2. `config.title` (role like "Business Researcher") → primary; no subtitle.
 *   3. Title-cased `config.config_id` → primary; no subtitle. Fallback for
 *      legacy unmigrated docs.
 *
 * Centralising this in one place prevents drift between surfaces — every
 * agent renders the same way regardless of where the component lives.
 */
export function displayNameFor(config: {
  name: string | null;
  title: string | null;
  config_id: string;
}): AgentDisplay {
  const titleFallback = config.config_id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const primary = config.name || config.title || titleFallback;
  const subtitle = config.name && config.title ? config.title : null;
  return { primary, subtitle };
}

// ─── API client functions ─────────────────────────────────────────────────────

export async function listAgentConfigs(
  accountId: string,
  opts: { visibleInFrontend?: boolean } = {},
): Promise<MergedAgentConfig[]> {
  const params: Record<string, string> = {};
  if (opts.visibleInFrontend) {
    params["visible_in_frontend"] = "true";
  }
  const { data } = await api.get<MergedAgentConfig[]>(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/agent-configs/`,
    { params },
  );
  return data;
}

export async function getAgentConfig(
  accountId: string,
  configId: string,
): Promise<MergedAgentConfig> {
  const { data } = await api.get<MergedAgentConfig>(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/agent-configs/${encodeURIComponent(configId)}`,
  );
  return data;
}

export async function createAgentConfig(
  accountId: string,
  body: AgentConfigCreate,
): Promise<MergedAgentConfig> {
  const { data } = await api.post<MergedAgentConfig>(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/agent-configs/`,
    body,
  );
  return data;
}

export async function upsertAgentConfigOverlay(
  accountId: string,
  configId: string,
  body: AgentConfigOverlayUpdate,
): Promise<MergedAgentConfig> {
  const { data } = await api.put<MergedAgentConfig>(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/agent-configs/${encodeURIComponent(configId)}`,
    body,
  );
  return data;
}

export async function deleteAgentConfig(
  accountId: string,
  configId: string,
): Promise<void> {
  await api.delete(
    `/api/v1/accounts/${encodeURIComponent(accountId)}/agent-configs/${encodeURIComponent(configId)}`,
  );
}
