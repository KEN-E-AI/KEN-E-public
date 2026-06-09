import api from "@/lib/api";

export type EarlyReleaseAdminConfigResponse = {
  code: string;
  is_active: boolean;
  expires_at: string | null;
  updated_by: string;
  updated_at: string;
  redemption_count: number;
};

export type EarlyReleaseAdminUpdateRequest = {
  code?: string;
  is_active?: boolean;
  expires_at?: string | null;
};

export type EarlyReleaseRedemption = {
  user_id: string;
  email: string;
  org_id: string;
  redeemed_at: string;
};

export type EarlyReleaseRedemptionsListResponse = {
  redemptions: EarlyReleaseRedemption[];
  total: number;
  next_cursor: string | null;
};

export function getEarlyReleaseConfig(): Promise<EarlyReleaseAdminConfigResponse> {
  return api
    .get<EarlyReleaseAdminConfigResponse>("/api/v1/admin/early-release-code")
    .then((r) => r.data);
}

export function updateEarlyReleaseConfig(
  body: EarlyReleaseAdminUpdateRequest,
): Promise<EarlyReleaseAdminConfigResponse> {
  return api
    .put<EarlyReleaseAdminConfigResponse>(
      "/api/v1/admin/early-release-code",
      body,
    )
    .then((r) => r.data);
}

export function listEarlyReleaseRedemptions(
  cursor?: string,
): Promise<EarlyReleaseRedemptionsListResponse> {
  return api
    .get<EarlyReleaseRedemptionsListResponse>(
      "/api/v1/admin/early-release-code/redemptions",
      { params: cursor ? { cursor } : undefined },
    )
    .then((r) => r.data);
}
