import { useInfiniteQuery } from "@tanstack/react-query";
import { getFlagAudit } from "@/lib/featureFlags/adminClient";
import type { AuditListResponse } from "@/lib/featureFlags/adminClient";
import type { FlagKey, FeatureFlagAuditAction } from "@/lib/featureFlags/types";
import { featureFlagKeys } from "@/lib/featureFlags/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

// ─── Types ────────────────────────────────────────────────────────────────────

type Props = {
  flagKey: FlagKey;
};

// ─── Action badge variant map ─────────────────────────────────────────────────

type BadgeVariant =
  | "success"
  | "destructive"
  | "warning"
  | "info"
  | "secondary";

const ACTION_VARIANT: Record<FeatureFlagAuditAction, BadgeVariant> = {
  create: "success",
  update: "info",
  toggle_active: "warning",
  delete: "destructive",
};

// ─── Diff serializer ──────────────────────────────────────────────────────────

function safeDiffJson(diff: unknown): string {
  try {
    return JSON.stringify(diff, null, 2);
  } catch {
    return "<unserializable diff>";
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

export function FlagAuditList({ flagKey }: Props) {
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: [...featureFlagKeys.detail(flagKey), "audit-infinite"],
    queryFn: ({ pageParam }) =>
      getFlagAudit(flagKey, { cursor: pageParam as string | null }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage: AuditListResponse) => lastPage.next_cursor,
  });

  if (isLoading) {
    return (
      <div className="space-y-3 py-4" aria-label="Loading audit entries">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert variant="destructive" className="mt-4">
        <AlertTitle>Failed to load audit log</AlertTitle>
        <AlertDescription>
          Could not fetch the audit log. Please try again.
          <Button
            variant="outline"
            size="sm"
            className="mt-2 block"
            onClick={() => void refetch()}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const allEntries = data?.pages.flatMap((page) => page.entries) ?? [];

  if (allEntries.length === 0) {
    return (
      <p className="py-6 text-center text-[var(--color-text-tertiary)] text-[var(--text-body-sm)]">
        No audit entries yet.
      </p>
    );
  }

  return (
    <div className="space-y-3 py-4">
      {allEntries.map((entry) => (
        <div
          key={entry.audit_id}
          className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-4 py-3 space-y-2"
        >
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)] font-medium">
              {entry.actor_email}
            </span>
            <div className="flex items-center gap-2">
              <Badge variant={ACTION_VARIANT[entry.action]}>
                {entry.action}
              </Badge>
              <span className="text-[var(--text-body-xs)] text-[var(--color-text-tertiary)]">
                {new Date(entry.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          {entry.diff != null && Object.keys(entry.diff).length > 0 && (
            <details className="text-[var(--text-body-xs)]">
              <summary className="cursor-pointer text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] select-none">
                Show diff
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-[var(--radius-sm)] bg-[var(--color-bg-base)] p-2 text-[var(--color-text-secondary)] font-mono whitespace-pre-wrap break-words">
                {safeDiffJson(entry.diff)}
              </pre>
            </details>
          )}
        </div>
      ))}

      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}
