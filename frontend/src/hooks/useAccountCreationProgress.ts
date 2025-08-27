import { useEffect, useState } from "react";
import axios from "axios";
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
        // Get auth token if available
        const token = localStorage.getItem("authToken");

        const response = await axios.get<AccountCreationProgress>(
          `${import.meta.env.VITE_API_BASE_URL}/api/v1/accounts/${accountId}/creation-status`,
          {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          },
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
