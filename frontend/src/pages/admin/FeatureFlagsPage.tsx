import { useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useFeatureFlags } from "@/lib/featureFlags/hooks";
import { FlagTable } from "@/components/admin/featureFlags/FlagTable";
import { FlagEditDrawer } from "@/components/admin/featureFlags/FlagEditDrawer";
import type { FeatureFlag } from "@/lib/featureFlags/types";

export default function FeatureFlagsPage() {
  const { isLoading, isError, error, data, refetch } = useFeatureFlags();
  const [drawerOpen, setDrawerOpen] = useState(false);
  // null = create mode; a flag = edit mode. Kept while the drawer animates
  // closed so the exit transition can play before the variant resets.
  const [editTarget, setEditTarget] = useState<FeatureFlag | null>(null);

  const openCreate = () => {
    setEditTarget(null);
    setDrawerOpen(true);
  };
  const openEdit = (flag: FeatureFlag) => {
    setEditTarget(flag);
    setDrawerOpen(true);
  };

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-[var(--text-heading-lg)] font-bold text-[var(--color-text-primary)]">
          Feature Flags
        </h1>
        <p className="text-[var(--text-body-md)] text-[var(--color-text-secondary)] mt-1">
          Manage targeted rollouts and kill switches
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : isError ? (
        <Alert variant="destructive">
          <AlertTitle>Failed to load feature flags</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>
              The feature-flag list could not be retrieved, so targeting and
              kill switches are unavailable until this resolves.
              {error instanceof Error ? ` (${error.message})` : ""}
            </p>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <FlagTable
          flags={data ?? []}
          onCreate={openCreate}
          onRowClick={openEdit}
        />
      )}

      {editTarget ? (
        <FlagEditDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          mode="edit"
          flag={editTarget}
        />
      ) : (
        <FlagEditDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          mode="create"
        />
      )}
    </div>
  );
}
