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
    console.log("[useAccountCreationProgress] Hook called with accountId:", accountId);
    if (!accountId) return;

    let isSubscribed = true;
    let timeoutId: NodeJS.Timeout | null = null;
    let retryCount = 0;
    let successfulFetches = 0; // Track successful fetches for progressive delays
    const maxRetries = 100; // Allow many retries for long-running operations
    const startTime = Date.now(); // Track when we started polling
    
    const fetchProgress = async () => {
      if (!isSubscribed) return;
      
      try {
        // Use the configured api instance which handles auth automatically
        const response = await api.get<AccountCreationProgress>(
          `/api/v1/accounts/${accountId}/creation-status`
        );

        // Only update state if component is still subscribed
        if (!isSubscribed) return;

        if (response.data) {
          // Reset retry count on successful fetch
          retryCount = 0;
          successfulFetches++;
          
          console.log("[useAccountCreationProgress] Progress data received:", response.data);
          
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
            // Don't schedule next poll
            return;
          }
        }
        
        // Calculate progressive delay based on time elapsed
        // For long-running operations (5-10 minutes), we should reduce polling frequency
        const elapsedMinutes = (Date.now() - startTime) / 60000;
        let nextDelay: number;
        
        if (elapsedMinutes < 1) {
          // First minute: poll every 10 seconds
          nextDelay = 10000;
        } else if (elapsedMinutes < 3) {
          // 1-3 minutes: poll every 15 seconds
          nextDelay = 15000;
        } else if (elapsedMinutes < 5) {
          // 3-5 minutes: poll every 20 seconds
          nextDelay = 20000;
        } else {
          // After 5 minutes: poll every 30 seconds
          nextDelay = 30000;
        }
        
        // Schedule next poll with progressive delay
        if (isSubscribed) {
          console.log(`[Progress Poll] Scheduling next check in ${nextDelay/1000}s (elapsed: ${elapsedMinutes.toFixed(1)} min)`);
          timeoutId = setTimeout(fetchProgress, nextDelay);
        }
      } catch (error: any) {
        if (!isSubscribed) return;
        
        // Handle rate limiting with exponential backoff
        if (error?.response?.status === 429) {
          retryCount++;
          
          if (retryCount > maxRetries) {
            console.error("Max retries reached for progress polling");
            return;
          }
          
          // Exponential backoff for rate limiting: 30s, 60s, 120s...
          const backoffDelay = Math.min(30000 * Math.pow(2, retryCount - 1), 120000);
          
          console.warn(`Rate limit hit, retrying in ${backoffDelay / 1000}s (retry ${retryCount}/${maxRetries})`);
          
          // Schedule retry with backoff
          timeoutId = setTimeout(fetchProgress, backoffDelay);
        } else if (error?.response?.status >= 500) {
          // Server error - retry with backoff
          retryCount++;
          const backoffDelay = Math.min(15000 * Math.pow(2, Math.min(retryCount - 1, 3)), 60000);
          
          console.warn(`Server error, retrying in ${backoffDelay / 1000}s`);
          timeoutId = setTimeout(fetchProgress, backoffDelay);
        } else {
          // Other errors - use progressive delay based on elapsed time
          console.error("Failed to fetch account creation progress:", error);
          
          if (isSubscribed) {
            const elapsedMinutes = (Date.now() - startTime) / 60000;
            const nextDelay = elapsedMinutes < 3 ? 15000 : 30000;
            timeoutId = setTimeout(fetchProgress, nextDelay);
          }
        }
      }
    };

    // Initial fetch after short delay to ensure backend has started processing
    // Then polling will continue at 10-second intervals
    timeoutId = setTimeout(fetchProgress, 2000);

    // Cleanup
    return () => {
      isSubscribed = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [accountId]);

  return progress;
}
