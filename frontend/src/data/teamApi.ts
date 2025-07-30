import api from "@/lib/api";
import apiPublic from "@/lib/api-public";

export interface TeamMember {
  user_id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  access_level: "admin" | "view" | "owner";
  added_date?: string;
  account_permissions?: Record<string, "edit" | "view">; // Account ID -> access level
  is_super_admin?: boolean; // True if email ends with @ken-e.ai
}

export interface TeamMembersResponse {
  members: TeamMember[];
  total: number;
}

export interface InviteMemberData {
  email: string;
  access_level: "admin" | "view";
  account_permissions?: Record<string, "edit" | "view">; // Optional account permissions for view-role users
}

export interface UpdateMemberAccessData {
  access_level: "admin" | "view";
}

export interface Invitation {
  id: string;
  email: string;
  organization_id: string;
  organization_name: string;
  invited_by: string;
  inviter_name: string;
  access_level: "admin" | "view";
  status: "pending" | "accepted" | "expired" | "cancelled";
  invited_at: string; // Changed from created_at to match backend
  expires_at: string;
  invitation_token?: string;
  accepted_at?: string;
  accepted_by?: string;
  account_permissions?: Record<string, "edit" | "view">; // Account permissions for view-role invitations
}

export interface InvitationListResponse {
  invitations: Invitation[];
  total: number;
}

export interface AcceptInvitationData {
  user_id: string;
  user_email: string;
  user_name?: string;
}

/**
 * Get all members of an organization
 */
export async function getOrganizationMembers(
  organizationId: string,
  accountId: string,
): Promise<TeamMembersResponse> {
  try {
    const response = await api.get(
      `/api/v1/firestore/organizations/${organizationId}/members`,
      {
        params: { account_id: accountId },
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error fetching organization members:", error);
    throw error;
  }
}

/**
 * Invite a new member to the organization
 */
export async function inviteMemberToOrganization(
  organizationId: string,
  data: InviteMemberData,
  currentUserId: string,
  currentUserName: string,
  organizationName: string,
): Promise<{ success: boolean; message: string }> {
  try {
    console.log("[teamApi] Inviting member with data:", {
      url: `/api/v1/firestore/organizations/${organizationId}/members/invite`,
      body: data,
      params: {
        current_user_id: currentUserId,
        current_user_name: currentUserName,
        organization_name: organizationName,
      },
    });

    const response = await api.post(
      `/api/v1/firestore/organizations/${organizationId}/members/invite`,
      data,
      {
        params: {
          current_user_id: currentUserId,
          current_user_name: currentUserName,
          organization_name: organizationName,
        },
      },
    );
    return response.data;
  } catch (error: any) {
    console.error("[teamApi] Error inviting member:", error);
    if (error.response) {
      console.error("[teamApi] Error response:", {
        status: error.response.status,
        data: error.response.data,
        headers: error.response.headers,
      });
    }
    throw error;
  }
}

/**
 * Update a member's access level
 */
export async function updateMemberAccessLevel(
  organizationId: string,
  userId: string,
  data: UpdateMemberAccessData,
  accountId: string,
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await api.put(
      `/api/v1/firestore/organizations/${organizationId}/members/${userId}`,
      data,
      {
        params: { account_id: accountId },
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error updating member access:", error);
    throw error;
  }
}

/**
 * Remove a member from the organization
 */
export async function removeMemberFromOrganization(
  organizationId: string,
  userId: string,
  accountId: string,
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await api.delete(
      `/api/v1/firestore/organizations/${organizationId}/members/${userId}`,
      {
        params: { account_id: accountId },
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error removing member:", error);
    throw error;
  }
}

/**
 * Get all invitations for an organization
 */
export async function getOrganizationInvitations(
  organizationId: string,
  accountId: string,
  status?: "pending" | "accepted" | "expired",
): Promise<InvitationListResponse> {
  try {
    const response = await api.get(
      `/api/v1/firestore/organizations/${organizationId}/invitations`,
      {
        params: {
          account_id: accountId,
          ...(status && { status }),
        },
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error fetching invitations:", error);
    throw error;
  }
}

/**
 * Verify an invitation token
 */
export async function verifyInvitationToken(
  token: string,
): Promise<Invitation> {
  try {
    const response = await apiPublic.get(
      `/api/v1/firestore/invitations/verify/${token}`,
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error verifying invitation:", error);
    throw error;
  }
}

/**
 * Accept an invitation
 */
export async function acceptInvitation(
  token: string,
  data: AcceptInvitationData,
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await apiPublic.post(
      `/api/v1/firestore/invitations/accept/${token}`,
      data,
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error accepting invitation:", error);
    throw error;
  }
}

/**
 * Cancel a pending invitation
 */
export async function cancelInvitation(
  invitationId: string,
  accountId: string,
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await api.delete(
      `/api/v1/firestore/invitations/${invitationId}`,
      {
        params: { account_id: accountId },
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error canceling invitation:", error);
    throw error;
  }
}

/**
 * Grant account access to a user
 */
export async function grantAccountAccess(
  accountId: string,
  userId: string,
  accessLevel: "edit" | "view",
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await api.post(
      `/api/v1/accounts/${accountId}/grant-access`,
      {
        user_id: userId,
        access_level: accessLevel,
      },
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error granting account access:", error);
    throw error;
  }
}

/**
 * Revoke account access from a user
 */
export async function revokeAccountAccess(
  accountId: string,
  userId: string,
): Promise<{ success: boolean; message: string }> {
  try {
    const response = await api.delete(
      `/api/v1/accounts/${accountId}/revoke-access/${userId}`,
    );
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error revoking account access:", error);
    throw error;
  }
}

/**
 * Get users with access to a specific account
 */
export async function getAccountPermissions(accountId: string): Promise<{
  account_id: string;
  permissions: Array<{
    user_id: string;
    email: string;
    access_level: string;
    first_name?: string;
    last_name?: string;
  }>;
  total: number;
}> {
  try {
    const response = await api.get(`/api/v1/accounts/${accountId}/permissions`);
    return response.data;
  } catch (error) {
    console.error("[teamApi] Error getting account permissions:", error);
    throw error;
  }
}
