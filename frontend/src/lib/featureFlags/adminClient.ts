// Typed axios wrappers for the Feature Flags admin API (super-admin only).
import api from "@/lib/api";
import type { FeatureFlag, FeatureFlagAuditEntry, FlagKey } from "./types";

// ─── Request body types ───────────────────────────────────────────────────────

export type FeatureFlagCreate = Omit<FeatureFlag, "created_at" | "updated_at">;

// PUT is a full replace; same shape as create. Aliased for call-site clarity.
export type FeatureFlagUpdate = FeatureFlagCreate;

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
  params.set("limit", String(Math.min(Math.max(1, opts.limit ?? 50), 200)));
  if (opts.cursor != null) {
    params.set("cursor", opts.cursor);
  }
  const { data } = await api.get<AuditListResponse>(
    `${BASE}/${encodeURIComponent(key)}/audit?${params.toString()}`,
  );
  return data;
}
