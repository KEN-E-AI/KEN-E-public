import { useState, useCallback } from "react";
import type { ProgressInfo } from "@/components/ui/loading-overlay";

export interface OperationState {
  isLoading: boolean;
  message: string;
  subMessage?: string;
  progress?: ProgressInfo;
}

export function useOperationLoading() {
  const [operationState, setOperationState] = useState<OperationState>({
    isLoading: false,
    message: "",
    subMessage: undefined,
    progress: undefined,
  });

  const startOperation = useCallback(
    (message: string, subMessage?: string, progress?: ProgressInfo) => {
      setOperationState({
        isLoading: true,
        message,
        subMessage,
        progress,
      });
    },
    [],
  );

  const endOperation = useCallback(() => {
    setOperationState({
      isLoading: false,
      message: "",
      subMessage: undefined,
      progress: undefined,
    });
  }, []);

  const updateOperationMessage = useCallback(
    (message: string, subMessage?: string) => {
      setOperationState((prev) => ({
        ...prev,
        message,
        subMessage,
      }));
    },
    [],
  );

  const updateOperationProgress = useCallback((progress: ProgressInfo) => {
    setOperationState((prev) => ({
      ...prev,
      progress,
    }));
  }, []);

  return {
    operationState,
    startOperation,
    endOperation,
    updateOperationMessage,
    updateOperationProgress,
  };
}
