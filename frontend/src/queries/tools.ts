import { useQuery } from "@tanstack/react-query";
import { getAccountTools } from "@/lib/api/tools";

// ─── Query key factory ────────────────────────────────────────────────────────

export const accountToolKeys = {
  all: ["accountTools"] as const,
  lists: () => [...accountToolKeys.all, "list"] as const,
  list: (accountId: string) => [...accountToolKeys.lists(), accountId] as const,
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Fetch the tool inventory available to one account.
 *
 * The inventory is the union of built-in function tools (always present) plus
 * tools whose owning MCP server has a matching connected integration on the
 * account. The picker renders the response grouped by source.
 *
 * Disabled when ``accountId`` is falsy so callers can wire it up before a
 * working account context exists without firing a doomed request.
 */
export function useAccountTools(accountId: string | null | undefined) {
  return useQuery({
    queryKey: accountToolKeys.list(accountId ?? ""),
    queryFn: () => getAccountTools(accountId!),
    enabled: !!accountId,
    staleTime: 1000 * 60,
  });
}
