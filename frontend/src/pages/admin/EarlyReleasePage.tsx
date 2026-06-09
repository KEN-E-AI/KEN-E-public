import { useState, useEffect, useRef } from "react";
import { Copy, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  useEarlyReleaseConfig,
  useUpdateEarlyReleaseConfig,
  useEarlyReleaseRedemptions,
} from "@/queries/earlyRelease";
import { RotateCodeDialog } from "@/components/admin/earlyRelease/RotateCodeDialog";
import { RedemptionsTable } from "@/components/admin/earlyRelease/RedemptionsTable";
import type {
  EarlyReleaseAdminUpdateRequest,
  EarlyReleaseRedemption,
} from "@/data/admin-earlyReleaseApi";

export default function EarlyReleasePage() {
  const { data, isLoading, isError, error, refetch } = useEarlyReleaseConfig();
  const updateMutation = useUpdateEarlyReleaseConfig();

  const [rotateDialogOpen, setRotateDialogOpen] = useState(false);
  const [rotateServerError, setRotateServerError] = useState<string | null>(
    null,
  );
  const [optimisticActive, setOptimisticActive] = useState<boolean | null>(
    null,
  );

  // Cursor-paginated redemptions — accumulate pages client-side
  const [redemptionCursor, setRedemptionCursor] = useState<string | undefined>(
    undefined,
  );
  const [allRedemptions, setAllRedemptions] = useState<
    EarlyReleaseRedemption[]
  >([]);
  const seenCursors = useRef<Set<string | undefined>>(new Set());

  const {
    data: redemptionsPage,
    isLoading: isRedemptionsLoading,
    isFetching: isRedemptionsFetching,
  } = useEarlyReleaseRedemptions(redemptionCursor);

  // Append new pages to the accumulated list
  useEffect(() => {
    if (!redemptionsPage) return;
    if (seenCursors.current.has(redemptionCursor)) return;
    seenCursors.current.add(redemptionCursor);
    setAllRedemptions((prev) => {
      const existingIds = new Set(prev.map((r) => r.user_id));
      const fresh = redemptionsPage.redemptions.filter(
        (r) => !existingIds.has(r.user_id),
      );
      return fresh.length > 0 ? [...prev, ...fresh] : prev;
    });
  }, [redemptionsPage, redemptionCursor]);

  const handleLoadMore = () => {
    if (redemptionsPage?.next_cursor) {
      setRedemptionCursor(redemptionsPage.next_cursor);
    }
  };

  const isUnset =
    isError &&
    (error as { response?: { status?: number } })?.response?.status === 404;

  const isActive = optimisticActive ?? data?.is_active ?? false;

  const handleToggleActive = () => {
    const next = !isActive;
    setOptimisticActive(next);
    updateMutation.mutate(
      { is_active: next },
      {
        onSuccess: () => {
          setOptimisticActive(null);
        },
        onError: (err: unknown) => {
          setOptimisticActive(null);
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
      },
    );
  };

  const handleCopyCode = async () => {
    if (!data?.code) return;
    try {
      await navigator.clipboard.writeText(data.code);
      toast.success("Code copied to clipboard");
    } catch {
      toast.error("Failed to copy code to clipboard");
    }
  };

  const handleRotate = (req: EarlyReleaseAdminUpdateRequest) => {
    setRotateServerError(null);
    updateMutation.mutate(req, {
      onSuccess: () => {
        setRotateDialogOpen(false);
        toast.success("Early Release code updated");
      },
      onError: (err: unknown) => {
        const axiosErr = err as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        const detail =
          axiosErr.response?.data?.detail ??
          axiosErr.message ??
          "Unknown error";
        setRotateServerError(detail);
      },
    });
  };

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-[var(--text-heading-lg)] font-bold text-[var(--color-text-primary)]">
          Early Release
        </h1>
        <p className="text-[var(--text-body-md)] text-[var(--color-text-secondary)] mt-1">
          Manage the shared early-access code
        </p>
      </div>

      {/* Status card */}
      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-32 w-full" />
        </div>
      ) : isError && !isUnset ? (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>Failed to load Early Release config.</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
            >
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : isUnset ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card p-4 space-y-3">
          <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
            <KeyRound className="h-4 w-4" />
            <span className="text-[var(--text-body-md)]">
              No Early Release code has been set yet.
            </span>
          </div>
          <Button
            type="button"
            onClick={() => setRotateDialogOpen(true)}
            size="sm"
          >
            Set initial code
          </Button>
        </div>
      ) : data ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card p-4 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="space-y-1">
              <p className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
                Current code
              </p>
              <div className="flex items-center gap-2">
                <code className="font-mono text-[var(--text-body-md)] text-[var(--color-text-primary)] bg-[var(--color-bg-subtle)] px-2 py-0.5 rounded">
                  {data.code}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyCode}
                  aria-label="Copy code"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <Badge
              variant={isActive ? "default" : "secondary"}
              className="shrink-0"
            >
              {isActive ? "Active" : "Disabled"}
            </Badge>
          </div>

          <div className="flex items-center gap-3">
            <Switch
              id="er-active-toggle"
              checked={isActive}
              onCheckedChange={handleToggleActive}
              disabled={updateMutation.isPending}
              aria-label="Toggle early release code active state"
            />
            <Label htmlFor="er-active-toggle" className="cursor-pointer">
              {isActive ? "Code is active" : "Code is disabled"}
            </Label>
          </div>

          <div className="grid grid-cols-2 gap-4 text-[var(--text-body-sm)]">
            {data.expires_at && (
              <div>
                <p className="text-[var(--color-text-secondary)]">Expires</p>
                <p className="text-[var(--color-text-primary)]">
                  {formatDate(data.expires_at)}
                </p>
              </div>
            )}
            <div>
              <p className="text-[var(--color-text-secondary)]">Redemptions</p>
              <p className="text-[var(--color-text-primary)] font-medium">
                {data.redemption_count}
              </p>
            </div>
            <div>
              <p className="text-[var(--color-text-secondary)]">
                Last updated by
              </p>
              <p className="text-[var(--color-text-primary)]">
                {data.updated_by}
              </p>
            </div>
            <div>
              <p className="text-[var(--color-text-secondary)]">Updated at</p>
              <p className="text-[var(--color-text-primary)]">
                {formatDate(data.updated_at)}
              </p>
            </div>
          </div>

          <div className="pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRotateDialogOpen(true)}
            >
              Set / Rotate code
            </Button>
          </div>
        </div>
      ) : null}

      {/* Redemptions section — shown only once config has loaded successfully
          (hidden during loading, on error, and in the unset/404 state) */}
      {!isLoading && !isError && data && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card p-4 space-y-3">
          <h2 className="text-[var(--text-body-md)] font-bold text-[var(--color-text-primary)]">
            Redemptions
          </h2>
          <RedemptionsTable
            redemptions={allRedemptions}
            nextCursor={redemptionsPage?.next_cursor ?? null}
            isLoading={isRedemptionsLoading}
            isLoadingMore={isRedemptionsFetching && !!redemptionCursor}
            onLoadMore={handleLoadMore}
          />
        </div>
      )}

      <RotateCodeDialog
        open={rotateDialogOpen}
        onOpenChange={(open) => {
          setRotateDialogOpen(open);
          if (!open) setRotateServerError(null);
        }}
        onRotate={handleRotate}
        isPending={updateMutation.isPending}
        serverError={rotateServerError}
      />
    </div>
  );
}
