import { useState, useCallback } from "react";
import { getChildOrganizationsWithAccounts } from "@/data/organizationApi";

interface UseChildOrganizationsReturn {
  childOrganizations: Record<string, any>[];
  loading: boolean;
  error: string | null;
  fetchChildOrganizations: (parentOrgId: string) => Promise<void>;
  clearChildOrganizations: () => void;
}

/**
 * Custom hook for managing child organizations state and operations.
 * Uses the optimized batch endpoint to fetch child organizations with their accounts
 * in a single request, avoiding the N+1 query problem.
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
      // Use the new batch endpoint that fetches children with accounts in one request
      const childOrgMetadata = await getChildOrganizationsWithAccounts(
        parentOrgId,
        true,
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
