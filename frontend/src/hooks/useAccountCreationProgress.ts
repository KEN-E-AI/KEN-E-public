import { useEffect, useState } from "react";
import api from "@/lib/api";
import type {
  ProgressInfo,
  ProgressStep,
} from "@/components/ui/loading-overlay";

interface AccountCreationProgress {
  status: "pending" | "processing" | "completed" | "failed";
  percentage: number;
  current_step: number;
  total_steps: number;
  message: string;
  steps: ProgressStep[];
}

export function useAccountCreationProgress(accountId: string | null) {
  const [progress, setProgress] = useState<ProgressInfo | null>(null);

  useEffect(() => {
    if (!accountId) return;

    let isSubscribed = true;
    let intervalId: NodeJS.Timeout | null = null;

    const fetchProgress = async () => {
      try {
        // Use the configured api instance which handles auth automatically
        const response = await api.get<AccountCreationProgress>(
          `/api/v1/accounts/${accountId}/creation-status`
        );

        // Only update state if component is still subscribed
        if (!isSubscribed) return;

        if (response.data) {
          setProgress({
            percentage: response.data.percentage,
            currentStep: response.data.current_step,
            totalSteps: response.data.total_steps,
            steps: response.data.steps,
          });

          // Stop polling if creation is complete or failed
          if (
            response.data.status === "completed" ||
            response.data.status === "failed"
          ) {
            // Clear the interval to stop polling
            if (intervalId) {
              clearInterval(intervalId);
              intervalId = null;
            }
          }
        }
      } catch (error: any) {
        // Only log non-rate-limit errors
        if (error?.response?.status !== 429) {
          console.error("Failed to fetch account creation progress:", error);
        }
        // Continue polling even on error (unless it's a rate limit)
        if (error?.response?.status === 429 && intervalId) {
          // Stop polling on rate limit
          clearInterval(intervalId);
          intervalId = null;
          console.warn("Rate limit hit, stopping progress polling");
        }
      }
    };

    // Initial fetch
    fetchProgress();

    // Set up polling interval
    // Poll every 3 seconds to avoid rate limiting (20 requests per minute max)
    intervalId = setInterval(fetchProgress, 3000);

    // Cleanup
    return () => {
      isSubscribed = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [accountId]); // Only depend on accountId, not isComplete

  return progress;
}
