import { useState, useCallback } from "react";
import {
  getChildOrganizations,
  getAccountsByOrganizationId,
} from "@/data/organizationApi";

interface UseChildOrganizationsReturn {
  childOrganizations: Record<string, any>[];
  loading: boolean;
  error: string | null;
  fetchChildOrganizations: (parentOrgId: string) => Promise<void>;
  clearChildOrganizations: () => void;
}

/**
 * Custom hook for managing child organizations state and operations
 */
export function useChildOrganizations(): UseChildOrganizationsReturn {
  const [childOrganizations, setChildOrganizations] = useState<
    Record<string, any>[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChildOrganizations = useCallback(async (parentOrgId: string) => {
    setLoading(true);
    setError(null);

    try {
      const childOrgs = await getChildOrganizations(parentOrgId);
      const childOrgMetadata = await Promise.all(
        childOrgs.map(async (childOrg) => {
          const accounts = await getAccountsByOrganizationId(
            childOrg.organization_id,
          );
          return {
            ...childOrg,
            accounts,
          };
        }),
      );
      setChildOrganizations(childOrgMetadata);
    } catch (err) {
      console.error("Failed to fetch child organizations:", err);
      setError("Failed to load child organizations");
      setChildOrganizations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearChildOrganizations = useCallback(() => {
    setChildOrganizations([]);
    setError(null);
  }, []);

  return {
    childOrganizations,
    loading,
    error,
    fetchChildOrganizations,
    clearChildOrganizations,
  };
}
