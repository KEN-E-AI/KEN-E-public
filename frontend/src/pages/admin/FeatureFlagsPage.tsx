import { Skeleton } from "@/components/ui/skeleton";
import { useFeatureFlags } from "@/lib/featureFlags/hooks";

export default function FeatureFlagsPage() {
  const { isLoading } = useFeatureFlags();

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
      ) : (
        <div data-testid="feature-flags-content-slot" />
      )}
    </div>
  );
}
