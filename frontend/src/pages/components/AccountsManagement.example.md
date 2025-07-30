# AccountsManagement Loading State Implementation Guide

This guide shows how to implement the loading overlay system in the AccountsManagement component to prevent user interactions during account operations.

## Required Changes

### 1. Import the Hook

Add this import at the top of AccountsManagement.tsx:

```tsx
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
```

### 2. Initialize the Hook

Inside the AccountsManagement component, add:

```tsx
const { startOperation, endOperation, updateOperationMessage } =
  useAccountOperations();
```

### 3. Update handleCreateAccount Function

Replace the existing handleCreateAccount with:

```tsx
const handleCreateAccount = async () => {
  console.log("[AccountsManagement] handleCreateAccount called");

  if (!currentOrgId) {
    toast({
      title: "Error",
      description:
        "No organization selected. Please select an organization first.",
      variant: "destructive",
    });
    return;
  }

  if (!createAccountFormData.account_name || !createAccountFormData.industry) {
    toast({
      title: "Validation Error",
      description: "Please fill in required fields",
      variant: "destructive",
    });
    return;
  }

  try {
    // Start the loading overlay
    startOperation(
      "Creating account...",
      "Please wait while we set up your new account",
    );

    // Close the modal immediately to prevent duplicate clicks
    setIsCreateAccountModalOpen(false);

    // Create account in Neo4j
    const newAccount = await createAccountMutation.mutateAsync({
      accountName: createAccountFormData.account_name,
      organizationId: currentOrgId,
      industry: createAccountFormData.industry,
      status: createAccountFormData.status,
      websites: createAccountFormData.websites,
      timezone: createAccountFormData.timezone,
      dataRegion: createAccountFormData.data_region,
      region: createAccountFormData.region,
    });

    const newAccountId = newAccount.account_id;

    // Update loading message
    updateOperationMessage(
      "Setting up account features...",
      "Syncing holiday activities",
    );

    // If the new account has a region, sync holiday activity logs
    if (
      createAccountFormData.region &&
      createAccountFormData.region.length > 0
    ) {
      try {
        await syncHolidayMutation.mutateAsync(newAccountId);
      } catch (syncError) {
        console.error(
          "Error syncing holiday activities for new account:",
          syncError,
        );
      }
    }

    // Update loading message
    updateOperationMessage("Finalizing setup...", "Updating permissions");

    // Update permissions and context (existing code)
    // ... rest of the existing logic ...

    // Navigate to account settings
    navigate("/account-settings");

    // End the loading state
    endOperation();
  } catch (error: any) {
    // Make sure to end the loading state on error
    endOperation();

    console.error("[AccountsManagement] Error creating account:", error);
    const errorMessage =
      error.response?.data?.detail ||
      error.message ||
      "Failed to create account";
    toast({
      title: "Error",
      description: `Error: ${errorMessage}`,
      variant: "destructive",
    });
  }
};
```

### 4. Update handleSaveAccount Function

```tsx
const handleSaveAccount = async () => {
  if (!selectedAccount) return;

  try {
    // Start loading overlay
    startOperation("Updating account...", "Saving your changes");

    // Close modal to prevent interactions
    setIsModalOpen(false);

    // Check if region is changing
    const regionChanged =
      JSON.stringify(selectedAccount.region) !==
      JSON.stringify(editFormData.region);

    // Update account in Neo4j
    const updatedAccount = await updateAccountMutation.mutateAsync({
      accountId: selectedAccount.account_id,
      updates: {
        account_name: editFormData.account_name,
        industry: editFormData.industry,
        status: editFormData.status,
        websites: editFormData.websites,
        timezone: editFormData.timezone,
        data_region: editFormData.data_region,
        region: editFormData.region,
      },
    });

    // If region changed, sync holiday activity logs
    if (regionChanged) {
      updateOperationMessage(
        "Syncing holiday activities...",
        `Updating for regions: ${editFormData.region.join(", ")}`,
      );

      try {
        const syncResult = await syncHolidayMutation.mutateAsync(
          selectedAccount.account_id,
        );

        if (syncResult.data.errors && syncResult.data.errors.length > 0) {
          toast({
            title: "Partial Sync",
            description: `Holiday activities synced with ${syncResult.data.errors.length} warnings.`,
            variant: "default",
          });
        }
      } catch (error) {
        console.error("Error syncing holiday activities:", error);
      }
    }

    // Update contexts
    updateOperationMessage("Finalizing update...", "Refreshing data");

    // ... existing context update code ...

    // End loading state
    endOperation();

    setSelectedAccount(null);
    toast({
      title: "Success",
      description: "Account updated successfully.",
    });
  } catch (error) {
    endOperation();
    console.error("Error saving account:", error);
    toast({
      title: "Error",
      description: "Failed to update account. Please try again.",
      variant: "destructive",
    });
  }
};
```

### 5. Update handleDeleteAccount Function

```tsx
const handleDeleteAccount = async () => {
  const account = selectedAccount;
  if (!account || deleteAccountMutation.isPending) {
    if (!account) {
      toast({
        title: "Error",
        description: "No account selected for deletion",
        variant: "destructive",
      });
    }
    return;
  }

  const accountId = account.account_id;
  const accountName = account.account_name;
  const isDeletingCurrentAccount = accountId === selectedOrgAccount?.accountId;

  // Close ALL dialogs immediately
  setIsDeleteDialogOpen(false);
  setIsModalOpen(false);
  setIsEditRegionPopoverOpen(false);
  setIsCreateRegionPopoverOpen(false);
  setIsMoveAccountDialogOpen(false);
  setSelectedAccount(null);

  try {
    // Start loading overlay with specific message
    startOperation(
      "Deleting account...",
      `Removing "${accountName}" and all associated data`,
    );

    // If deleting the current account, clear auth state immediately
    if (isDeletingCurrentAccount) {
      const newAccountMetadata = { ...accountMetadata };
      delete newAccountMetadata[accountId];
      setAccountMetadata(newAccountMetadata);
      setSelectedOrgAccount(null);
    }

    await deleteAccountMutation.mutateAsync({
      orgId: currentOrgId!,
      accountId: accountId,
    });

    // End loading state
    endOperation();

    toast({
      title: "Account Deleted",
      description: `"${accountName}" and all related entities have been permanently deleted.`,
    });

    // Update metadata if not current account
    if (!isDeletingCurrentAccount) {
      // ... existing metadata update code ...
    }

    // Navigate if we deleted the current account
    if (isDeletingCurrentAccount) {
      navigate("/workspace-selection");
    }
  } catch (error: any) {
    endOperation();
    console.error("[AccountsManagement] Error deleting account:", error);
    const errorMessage =
      error.response?.data?.detail ||
      error.message ||
      "Failed to delete account";
    toast({
      title: "Error",
      description: `Error: ${errorMessage}`,
      variant: "destructive",
    });
  }
};
```

### 6. Update handleMoveAccount Function

```tsx
const handleMoveAccount = async () => {
  // ... existing validation code ...

  try {
    // Start loading overlay
    startOperation(
      "Moving account...",
      `Transferring "${selectedAccount.account_name}" to "${targetOrg.organization_name}"`,
    );

    // Close dialogs
    setIsMoveAccountDialogOpen(false);
    setIsModalOpen(false);

    await moveAccount(
      currentOrgId,
      selectedAccount.account_id,
      targetOrganizationId,
    );

    // ... existing context update code ...

    endOperation();

    toast({
      title: "Account Moved",
      description: `"${selectedAccount.account_name}" has been moved successfully.`,
    });
  } catch (error: any) {
    endOperation();
    console.error("[AccountsManagement] Error moving account:", error);
    toast({
      title: "Error",
      description: `Error: ${error.response?.data?.detail || error.message}`,
      variant: "destructive",
    });
  }
};
```

## Additional UI Improvements

### 1. Disable Buttons During Mutations

Update button disabled states to also check for operation in progress:

```tsx
const { isOperationInProgress } = useAccountOperations();

// In create button
<Button
  onClick={handleCreateAccount}
  disabled={createAccountMutation.isPending || isOperationInProgress}
>
  {createAccountMutation.isPending ? "Creating..." : "Create Account"}
</Button>

// In save button
<Button
  onClick={handleSaveAccount}
  disabled={updateAccountMutation.isPending || isOperationInProgress}
>
  {updateAccountMutation.isPending ? "Saving..." : "Save Changes"}
</Button>
```

### 2. Prevent Modal Interactions

Add a check to prevent opening modals during operations:

```tsx
const handleEditAccount = (account: Account) => {
  if (isOperationInProgress) return;
  // ... rest of existing code
};
```

## Benefits

1. **Clear User Feedback**: Users see what's happening with descriptive messages
2. **Prevents Duplicate Actions**: UI is blocked during operations
3. **Consistent Experience**: All account operations use the same loading pattern
4. **Error Recovery**: Loading state is properly cleared on errors
5. **Progressive Updates**: Messages update as operations progress

## Testing

To test the implementation:

1. Create a new account and verify the loading overlay appears
2. Try clicking elsewhere during creation - should be blocked
3. Update account regions to trigger sync - verify multi-step messages
4. Delete an account - verify immediate UI blocking
5. Test error scenarios - verify loading state clears properly
