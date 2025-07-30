import React, { createContext, useContext, ReactNode } from "react";
import { useOperationLoading } from "@/hooks/useOperationLoading";
import { LoadingOverlay } from "@/components/ui/loading-overlay";

interface AccountOperationsContextType {
  startOperation: (message: string, subMessage?: string) => void;
  endOperation: () => void;
  updateOperationMessage: (message: string, subMessage?: string) => void;
  isOperationInProgress: boolean;
}

const AccountOperationsContext = createContext<
  AccountOperationsContextType | undefined
>(undefined);

export function AccountOperationsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const {
    operationState,
    startOperation,
    endOperation,
    updateOperationMessage,
  } = useOperationLoading();

  return (
    <AccountOperationsContext.Provider
      value={{
        startOperation,
        endOperation,
        updateOperationMessage,
        isOperationInProgress: operationState.isLoading,
      }}
    >
      <div className="relative">
        {children}
        <LoadingOverlay
          isLoading={operationState.isLoading}
          message={operationState.message}
          subMessage={operationState.subMessage}
          variant="fullscreen"
        />
      </div>
    </AccountOperationsContext.Provider>
  );
}

export function useAccountOperations() {
  const context = useContext(AccountOperationsContext);
  if (context === undefined) {
    throw new Error(
      "useAccountOperations must be used within an AccountOperationsProvider",
    );
  }
  return context;
}
