import { useQuery } from "@tanstack/react-query";
import {
  getOrganizations,
  getOrganizationsBatch,
} from "@/data/organizationApi";
import { useAuth } from "@/contexts/AuthContext";

export type WorkspaceOptions = {
  orgMetadata: Record<string, any>;
  accountMetadata: Record<string, any>;
};

/**
 * Fetches every organization (and its accounts) the current user can access,
 * shaped as the orgMetadata/accountMetadata records AuthContext consumers expect.
 *
 * `GET /api/v1/organizations/` already filters server-side — the full set for
 * super admins, the membership-scoped set for everyone else — so this hook is
 * the live source of truth for the workspace switcher. It replaces the stale
 * localStorage snapshot that was written once during the /select-organization
 * flow and never refreshed afterwards.
 */
export function useWorkspaceOptions() {
  const { user, isAuthenticated } = useAuth();

  return useQuery<WorkspaceOptions>({
    queryKey: ["workspace-options", user?.id],
    enabled: isAuthenticated && Boolean(user?.id),
    staleTime: 60_000,
    queryFn: async () => {
      const organizations = await getOrganizations();
      const orgIds = organizations.map((org) => org.organization_id);
      const batch = await getOrganizationsBatch(orgIds, true);

      const orgMetadata: Record<string, any> = {};
      const accountMetadata: Record<string, any> = {};

      for (const org of organizations) {
        // The batch endpoint carries the accounts array; fall back to the bare
        // org record if a particular org failed to resolve in the batch.
        const detailed = batch[org.organization_id];
        orgMetadata[org.organization_id] = detailed ?? org;
        for (const account of detailed?.accounts ?? []) {
          accountMetadata[account.account_id] = account;
        }
      }

      return { orgMetadata, accountMetadata };
    },
  });
}
