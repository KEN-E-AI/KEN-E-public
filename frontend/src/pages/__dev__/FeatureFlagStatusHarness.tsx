import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { useFeatureFlagsContext } from "@/contexts/FeatureFlagsContext";
import type { FlagKey } from "@/lib/featureFlags/types";

const E2E_FLAG_KEY = "e2e_test_flag" as FlagKey;

export function FeatureFlagStatusHarness() {
  const { enabled, reason, isLoading } = useFeatureFlag(E2E_FLAG_KEY);
  const { refetch } = useFeatureFlagsContext();

  return (
    <div style={{ padding: "1rem", fontFamily: "monospace" }}>
      <h1>Feature Flag Status Harness</h1>
      <p>Flag: {E2E_FLAG_KEY}</p>
      <p data-testid="ff-enabled">{String(enabled)}</p>
      <p data-testid="ff-reason">{reason}</p>
      <p data-testid="ff-isloading">{String(isLoading)}</p>
      <button data-testid="ff-refetch" onClick={() => void refetch()}>
        Refetch
      </button>
    </div>
  );
}
