import { useEffect, useState, useRef } from "react";
import api from "@/lib/api";

interface AccountCreationStatus {
  status: "pending" | "processing" | "completed" | "failed";
  message: string;
}

interface SimplifiedProgress {
  status: "idle" | "processing" | "completed" | "failed";
  message: string;
}

export function useAccountCreationProgress(accountId: string | null): SimplifiedProgress {
  const [progress, setProgress] = useState<SimplifiedProgress>({
    status: "idle",
    message: "",
  });
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    console.log("[useAccountCreationProgress] Hook called with accountId:", accountId);
    if (!accountId) {
      setProgress({ status: "idle", message: "" });
      return;
    }

    let isSubscribed = true;
    let intervalId: NodeJS.Timeout | null = null;
    startTimeRef.current = Date.now();
    const maxPollingTime = 30 * 60 * 1000; // 30 minutes timeout

    const checkStatus = async () => {
      if (!isSubscribed) return;

      // Check if we've exceeded max polling time
      if (Date.now() - startTimeRef.current > maxPollingTime) {
        console.log("[useAccountCreationProgress] Max polling time exceeded, stopping");
        if (intervalId) {
          clearInterval(intervalId);
        }
        setProgress({
          status: "failed",
          message: "Account creation is taking longer than expected. Please refresh the page.",
        });
        return;
      }

      try {
        const response = await api.get<AccountCreationStatus>(
          `/api/v1/accounts/${accountId}/creation-status`
        );

        if (!isSubscribed) return;

        if (response.data) {
          console.log("[useAccountCreationProgress] Status received:", response.data);
          
          setProgress({
            status: response.data.status as SimplifiedProgress["status"],
            message: response.data.message,
          });

          // Stop polling if completed or failed
          if (response.data.status === "completed" || response.data.status === "failed") {
            console.log("[useAccountCreationProgress] Creation finished, stopping polling");
            if (intervalId) {
              clearInterval(intervalId);
            }
          }
        }
      } catch (error: any) {
        if (!isSubscribed) return;
        
        console.error("[useAccountCreationProgress] Failed to check status:", error);
        
        // Don't update UI for transient errors, just log them
        // The polling will continue and may succeed on next attempt
      }
    };

    // Initial check immediately
    checkStatus();
    
    // Poll every 30 seconds (reduced from complex progressive delays)
    intervalId = setInterval(checkStatus, 30000);
    console.log("[useAccountCreationProgress] Started polling every 30 seconds");

    // Cleanup function
    return () => {
      console.log("[useAccountCreationProgress] Cleaning up polling");
      isSubscribed = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [accountId]);

  return progress;
}