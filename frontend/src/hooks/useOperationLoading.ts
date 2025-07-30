import { useState, useCallback } from "react";

export interface OperationState {
  isLoading: boolean;
  message: string;
  subMessage?: string;
}

export function useOperationLoading() {
  const [operationState, setOperationState] = useState<OperationState>({
    isLoading: false,
    message: "",
    subMessage: undefined,
  });

  const startOperation = useCallback((message: string, subMessage?: string) => {
    setOperationState({
      isLoading: true,
      message,
      subMessage,
    });
  }, []);

  const endOperation = useCallback(() => {
    setOperationState({
      isLoading: false,
      message: "",
      subMessage: undefined,
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

  return {
    operationState,
    startOperation,
    endOperation,
    updateOperationMessage,
  };
}
