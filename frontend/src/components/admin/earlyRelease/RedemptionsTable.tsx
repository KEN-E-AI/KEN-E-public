import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { EarlyReleaseRedemption } from "@/data/admin-earlyReleaseApi";

type Props = {
  redemptions: EarlyReleaseRedemption[];
  nextCursor: string | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

export function RedemptionsTable({
  redemptions,
  nextCursor,
  isLoading,
  isLoadingMore,
  onLoadMore,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Org ID</TableHead>
            <TableHead>Redeemed at</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {redemptions.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={3}
                className="text-center text-[var(--color-text-secondary)]"
              >
                No redemptions yet
              </TableCell>
            </TableRow>
          ) : (
            redemptions.map((r) => (
              <TableRow key={r.user_id}>
                <TableCell className="font-mono text-sm">{r.email}</TableCell>
                <TableCell className="font-mono text-sm text-[var(--color-text-secondary)]">
                  {r.org_id}
                </TableCell>
                <TableCell className="text-sm text-[var(--color-text-secondary)]">
                  {formatDate(r.redeemed_at)}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {nextCursor && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onLoadMore}
          disabled={isLoadingMore}
        >
          {isLoadingMore ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  );
}
