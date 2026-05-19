import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { featureFlagKeys, useUpdateFlag } from "@/lib/featureFlags/hooks";
import type { FeatureFlag } from "@/lib/featureFlags/types";

// ─── Types ────────────────────────────────────────────────────────────────────

type SortColumn = "updated_at" | "expected_ga_release";
type SortDirection = "asc" | "desc";

type Props = {
  flags: FeatureFlag[];
  onRowClick?: (flag: FeatureFlag) => void;
  onCreate?: () => void;
};

// ─── Sort helpers ─────────────────────────────────────────────────────────────

function compareExpectedGaRelease(
  a: string | null,
  b: string | null,
  direction: SortDirection,
): number {
  // Blanks always sort last regardless of direction
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  const cmp = a.localeCompare(b);
  return direction === "asc" ? cmp : -cmp;
}

function compareUpdatedAt(
  a: string,
  b: string,
  direction: SortDirection,
): number {
  const cmp = a.localeCompare(b);
  return direction === "asc" ? cmp : -cmp;
}

function sortFlags(
  flags: FeatureFlag[],
  column: SortColumn,
  direction: SortDirection,
): FeatureFlag[] {
  return [...flags].sort((a, b) => {
    if (column === "expected_ga_release") {
      return compareExpectedGaRelease(
        a.expected_ga_release,
        b.expected_ga_release,
        direction,
      );
    }
    return compareUpdatedAt(a.updated_at, b.updated_at, direction);
  });
}

// ─── Component ────────────────────────────────────────────────────────────────

export function FlagTable({ flags, onRowClick, onCreate }: Props) {
  const queryClient = useQueryClient();
  const updateFlag = useUpdateFlag();
  const [sortColumn, setSortColumn] = useState<SortColumn>("updated_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function handleGaReleaseHeaderClick() {
    if (sortColumn === "expected_ga_release") {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn("expected_ga_release");
      setSortDirection("asc");
    }
  }

  function handleToggleActive(flag: FeatureFlag) {
    const newActive = !flag.is_active;

    // Optimistic update: cancel in-flight list queries, snapshot, write toggled row
    const listKey = featureFlagKeys.list();
    queryClient.cancelQueries({ queryKey: listKey });
    const previousFlags = queryClient.getQueryData<FeatureFlag[]>(listKey);
    queryClient.setQueryData<FeatureFlag[]>(listKey, (old) =>
      (old ?? []).map((f) =>
        f.key === flag.key ? { ...f, is_active: newActive } : f,
      ),
    );

    updateFlag.mutate(
      {
        key: flag.key,
        body: {
          key: flag.key,
          description: flag.description,
          default_enabled: flag.default_enabled,
          is_active: newActive,
          targeting_rules: flag.targeting_rules,
          bucketing_entity: flag.bucketing_entity,
          owner: flag.owner,
          expected_ga_release: flag.expected_ga_release,
        },
      },
      {
        onError: (err: unknown) => {
          // Revert optimistic update
          queryClient.setQueryData<FeatureFlag[]>(listKey, previousFlags);
          const axiosErr = err as {
            response?: { data?: { detail?: string } };
            message?: string;
          };
          const detail =
            axiosErr.response?.data?.detail ??
            axiosErr.message ??
            "Unknown error";
          toast.error(detail);
        },
        onSuccess: () => {
          toast.success(
            "Kill switch applied. Fully effective within 60 s across all servers.",
          );
        },
      },
    );
  }

  if (flags.length === 0) {
    return (
      <div
        data-testid="feature-flags-table-empty"
        className="text-[var(--color-text-tertiary)] text-[var(--text-body-md)] py-6"
      >
        No feature flags yet.
      </div>
    );
  }

  const sorted = sortFlags(flags, sortColumn, sortDirection);

  return (
    <div className="space-y-3">
      {onCreate && (
        <div className="flex justify-end">
          <Button size="sm" onClick={onCreate}>
            + New flag
          </Button>
        </div>
      )}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Rollout %</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead
                className="cursor-pointer select-none hover:text-[var(--color-text-primary)]"
                onClick={handleGaReleaseHeaderClick}
                aria-sort={
                  sortColumn === "expected_ga_release"
                    ? sortDirection === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                GA Release
                {sortColumn === "expected_ga_release" && (
                  <span className="ml-1 text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((flag) => (
              <TableRow
                key={flag.key}
                className={onRowClick ? "cursor-pointer" : undefined}
                onClick={onRowClick ? () => onRowClick(flag) : undefined}
              >
                <TableCell className="font-mono text-[var(--text-body-sm)] text-[var(--color-text-primary)]">
                  {flag.key}
                </TableCell>
                <TableCell>
                  <span
                    className="block truncate max-w-[28ch] text-[var(--color-text-secondary)]"
                    title={flag.description}
                  >
                    {flag.description}
                  </span>
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Switch
                    checked={flag.is_active}
                    onCheckedChange={() => handleToggleActive(flag)}
                    aria-label={`Toggle ${flag.key} active state`}
                  />
                </TableCell>
                <TableCell>
                  <Badge
                    variant={flag.default_enabled ? "success" : "secondary"}
                  >
                    {flag.default_enabled ? "On" : "Off"}
                  </Badge>
                </TableCell>
                <TableCell className="text-[var(--color-text-secondary)]">
                  {flag.targeting_rules.rollout_percentage}%
                </TableCell>
                <TableCell className="text-[var(--color-text-secondary)] text-[var(--text-body-sm)]">
                  {flag.owner}
                </TableCell>
                <TableCell className="text-[var(--color-text-secondary)]">
                  {flag.expected_ga_release ?? "—"}
                </TableCell>
                <TableCell className="text-[var(--color-text-secondary)] text-[var(--text-body-sm)]">
                  {new Date(flag.updated_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
