import api from "@/lib/api";

export type SuperAdminEntry = {
  uid: string;
  email: string | null;
};

export type SuperAdminListResponse = {
  super_admins: SuperAdminEntry[];
  total: number;
};

export type GrantSuperAdminRequest =
  | { uid: string; email?: never }
  | { email: string; uid?: never };

export type RevokeResponse = {
  success: boolean;
  message: string;
  data: { uid: string };
};

export function listSuperAdmins(): Promise<SuperAdminListResponse> {
  return api
    .get<SuperAdminListResponse>("/api/v1/admin/super-admins")
    .then((r) => r.data);
}

export function grantSuperAdmin(
  body: GrantSuperAdminRequest,
): Promise<SuperAdminEntry> {
  return api
    .post<SuperAdminEntry>("/api/v1/admin/super-admins", body)
    .then((r) => r.data);
}

export function revokeSuperAdmin(uid: string): Promise<RevokeResponse> {
  return api
    .delete<RevokeResponse>(`/api/v1/admin/super-admins/${uid}`)
    .then((r) => r.data);
}
