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
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!accountId || isComplete) return;

    const fetchProgress = async () => {
      try {
        // Use the configured api instance which handles auth automatically
        const response = await api.get<AccountCreationProgress>(
          `/api/v1/accounts/${accountId}/creation-status`
        );

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
            setIsComplete(true);
          }
        }
      } catch (error) {
        console.error("Failed to fetch account creation progress:", error);
        // Continue polling even on error
      }
    };

    // Initial fetch
    fetchProgress();

    // Set up polling interval
    const interval = setInterval(fetchProgress, 1000); // Poll every second

    // Cleanup
    return () => clearInterval(interval);
  }, [accountId, isComplete]);

  return progress;
}
