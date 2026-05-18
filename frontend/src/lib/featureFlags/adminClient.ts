/**
 * Typed axios wrappers for the Feature Flags admin API.
 *
 * Endpoints: /api/v1/admin/feature-flags/*  (super-admin only)
 * Auth is handled by the shared `api` instance (Firebase JWT interceptor).
 */
import api from "@/lib/api";
import type { FeatureFlag, FeatureFlagAuditEntry, FlagKey } from "./types";

// ─── Request body types ───────────────────────────────────────────────────────

/** POST body: FeatureFlag without server-generated timestamps */
export type FeatureFlagCreate = Omit<FeatureFlag, "created_at" | "updated_at">;

/** PUT body: full replace of flag config; server fills updated_at */
export type FeatureFlagUpdate = Omit<FeatureFlag, "created_at" | "updated_at">;

// ─── Response types ───────────────────────────────────────────────────────────

export type FlagListResponse = { flags: FeatureFlag[] };

export type AuditListResponse = {
  entries: FeatureFlagAuditEntry[];
  next_cursor: string | null;
};

// ─── Client functions ─────────────────────────────────────────────────────────

const BASE = "/api/v1/admin/feature-flags";

export async function listFlags(): Promise<FeatureFlag[]> {
  const { data } = await api.get<FlagListResponse>(BASE);
  return data.flags;
}

export async function getFlag(key: FlagKey): Promise<FeatureFlag> {
  const { data } = await api.get<FeatureFlag>(
    `${BASE}/${encodeURIComponent(key)}`,
  );
  return data;
}

export async function createFlag(
  body: FeatureFlagCreate,
): Promise<FeatureFlag> {
  const { data } = await api.post<FeatureFlag>(BASE, body);
  return data;
}

export async function updateFlag(
  key: FlagKey,
  body: FeatureFlagUpdate,
): Promise<FeatureFlag> {
  const { data } = await api.put<FeatureFlag>(
    `${BASE}/${encodeURIComponent(key)}`,
    body,
  );
  return data;
}

export async function deleteFlag(key: FlagKey): Promise<void> {
  await api.delete(`${BASE}/${encodeURIComponent(key)}`);
}

export async function getFlagAudit(
  key: FlagKey,
  opts: { limit?: number; cursor?: string | null } = {},
): Promise<AuditListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  if (opts.cursor) {
    params.set("cursor", opts.cursor);
  }
  const { data } = await api.get<AuditListResponse>(
    `${BASE}/${encodeURIComponent(key)}/audit?${params.toString()}`,
  );
  return data;
}
