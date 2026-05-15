import { useState, useMemo, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import axios from "axios";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import { useToast } from "@/hooks/use-toast";
import {
  useAccounts,
  useCreateAccount,
  useInvalidateAccounts,
} from "@/queries/accounts";
import { useAccountCreationProgress } from "@/hooks/useAccountCreationProgress";
import { generateAccountId } from "@/lib/idGenerator";
import { getOrganizationById } from "@/data/organizationApi";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  User,
  Plus,
  Settings,
  Store,
  AlertTriangle,
  Info,
  Loader2,
} from "lucide-react";
import { type Organization } from "@/data/organizationTypes";
import { getIndustryDisplayName } from "@/lib/industryMigration";
import {
  AccountCreationWizard,
  type AccountCreationData,
} from "@/components/settings/AccountCreationWizard";
interface AccountsManagementProps {
  orgData: Organization;
  currentOrgId: string;
  openCreateModal?: boolean;
  hasAdminAccess?: boolean;
  accountsInSetup?: Set<string>;
  setAccountsInSetup?: React.Dispatch<React.SetStateAction<Set<string>>>;
}

const AccountsManagement = ({
  orgData,
  currentOrgId,
  openCreateModal = false,
  hasAdminAccess = true,
  accountsInSetup: accountsInSetupProp,
  setAccountsInSetup: setAccountsInSetupProp,
}: AccountsManagementProps) => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const {
    setAccountMetadata,
    user,
    setOrgMetadata,
    refreshNotifications,
    isSuperAdmin,
  } = useAuth();

  // Account operations context for loading overlay
  const {
    startOperation,
    endOperation,
    updateOperationMessage,
    isOperationInProgress,
  } = useAccountOperations();

  // React Query hooks
  const { data: accounts = [], isLoading: isLoadingAccounts } =
    useAccounts(currentOrgId);
  const createAccountMutation = useCreateAccount();
  const invalidateAccounts = useInvalidateAccounts();

  // State for tracking account creation
  const [creatingAccountId, setCreatingAccountId] = useState<string | null>(
    null,
  );

  // State for tracking accounts still being set up (strategy generation in progress)
  // Use prop if provided, otherwise use local state
  const [localAccountsInSetup, setLocalAccountsInSetup] = useState<Set<string>>(
    new Set(),
  );
  const accountsInSetup = accountsInSetupProp ?? localAccountsInSetup;
  const setAccountsInSetup = setAccountsInSetupProp ?? setLocalAccountsInSetup;

  // Hook for tracking account creation progress
  const accountCreationProgress = useAccountCreationProgress(creatingAccountId);

  // Update the operation message when progress changes (simplified)
  useEffect(() => {
    if (accountCreationProgress && accountCreationProgress.status !== "idle") {
      console.log(
        "[AccountsManagement] Progress update received:",
        accountCreationProgress,
      );

      // Update the operation message based on status
      if (accountCreationProgress.status === "processing") {
        updateOperationMessage(
          "Creating account...",
          accountCreationProgress.message,
        );
      }

      // Check if account creation is complete
      if (accountCreationProgress.status === "completed") {
        console.log(
          "[AccountsManagement] Account creation complete! Refreshing data...",
        );

        // Show success toast
        toast({
          title: "Success",
          description:
            "Account created successfully with all strategy documents!",
        });

        // Give user a moment to see the completion message, then refresh data
        setTimeout(async () => {
          // Refresh data once at completion to avoid rate limiting
          try {
            // Use manual cache invalidation instead of automatic refetch
            // This allows the component to control when to refresh
            invalidateAccounts(currentOrgId);

            // Refresh organization metadata (quick operation)
            const updatedOrg = await getOrganizationById(currentOrgId);

            if (updatedOrg) {
              // Use the accounts from the cache that will be populated when ready
              // instead of triggering a new fetch that might timeout
              setOrgMetadata((prev) => ({
                ...prev,
                [currentOrgId]: {
                  ...updatedOrg,
                  accounts: accounts || [], // Use the accounts from React Query cache
                },
              }));
            }

            // Refresh notifications
            await refreshNotifications();

            console.log(
              "[AccountsManagement] Cache invalidated successfully after account creation",
            );
          } catch (error) {
            console.error(
              "[AccountsManagement] Error refreshing data after account creation:",
              error,
            );
          } finally {
            // Always end the operation and clear the tracking ID
            endOperation();
            setCreatingAccountId(null);

            // Remove from accounts in setup
            if (creatingAccountId) {
              setAccountsInSetup((prev) => {
                const next = new Set(prev);
                next.delete(creatingAccountId);
                return next;
              });
            }
          }
        }, 2000); // 2 second delay to show completion
      }

      // Handle failure
      if (accountCreationProgress.status === "failed") {
        console.error("[AccountsManagement] Account creation failed");
        toast({
          title: "Error",
          description:
            accountCreationProgress.message ||
            "Account creation failed. Please try again.",
          variant: "destructive",
        });
        endOperation();
        setCreatingAccountId(null);

        // Remove from accounts in setup on failure
        if (creatingAccountId) {
          setAccountsInSetup((prev) => {
            const next = new Set(prev);
            next.delete(creatingAccountId);
            return next;
          });
        }
      }
    }
  }, [
    accountCreationProgress,
    updateOperationMessage,
    endOperation,
    toast,
    currentOrgId,
    setOrgMetadata,
    refreshNotifications,
  ]);

  // Debug: Log accounts data when it changes
  useEffect(() => {
    if (accounts && accounts.length > 0) {
      console.log("[AccountsManagement] Accounts loaded:", accounts);
      console.log("[AccountsManagement] First account full data:", accounts[0]);
      if (accounts[0].marketing_channels) {
        console.log(
          "[AccountsManagement] First account has marketing_channels:",
          accounts[0].marketing_channels,
        );
      }
    }
  }, [accounts]);

  // Helper functions for account creation (following C-4: simple, testable functions)
  const validateAccountCreation = (
    data: AccountCreationData,
    orgId: string | null,
  ): string | null => {
    if (!orgId) {
      return "No organization selected. Please select an organization first.";
    }
    if (!data.account_name || !data.industry) {
      return "Please fill in required fields: account name and industry.";
    }
    return null;
  };

  const transformWizardData = (data: AccountCreationData, orgId: string) => {
    const baseData = {
      accountName: data.account_name,
      organizationId: orgId,
      industry: data.industry,
      status: "Active" as const,
      websites: data.websites || [],
      timezone: data.timezone,
      dataRegion: data.data_region,
      region: data.region,
      estimatedAnnualAdBudget: data.estimated_annual_ad_budget || null,
      businessStrategyDocuments: data.business_strategy_documents || [],
      marketing_channels: data.marketing_channels || [],
      product_integrations: data.product_integrations || [],
      dry_run: data.dry_run ?? false,
    };

    // Only include strategy fields if user is super admin
    if (isSuperAdmin) {
      return {
        ...baseData,
        enabled_strategies: data.enabled_strategies,
        override_product_categories: data.override_product_categories,
      };
    }

    return baseData;
  };

  const updateContextsAfterCreation = (account: any, orgId: string) => {
    // Update account metadata for easy lookup
    setAccountMetadata((prev) => ({
      ...prev,
      [account.account_id]: account,
    }));

    // Update orgMetadata to include the new account
    setOrgMetadata((prev) => ({
      ...prev,
      [orgId]: {
        ...prev[orgId],
        accounts: [...(prev[orgId]?.accounts || []), account],
      },
    }));
  };

  // State for account creation
  const [isCreateAccountModalOpen, setIsCreateAccountModalOpen] =
    useState(false);

  // Filter accounts based on user permissions
  const organizationAccounts = useMemo(() => {
    // Super admins or organization admins have access to all accounts
    if (isSuperAdmin || hasAdminAccess) {
      return accounts;
    }

    // Regular users only see accounts they have explicit permissions for
    return accounts.filter((account) => {
      return (
        user?.permissions?.account_permissions?.[account.account_id] ||
        user?.permissions?.accounts?.[account.account_id] // Fallback for backward compatibility
      );
    });
  }, [
    accounts,
    user?.permissions?.account_permissions,
    user?.permissions?.accounts,
    isSuperAdmin,
    hasAdminAccess,
  ]);

  // Note: Account creation status polling is handled by useAccountCreationProgress hook
  // for the account currently being created. We don't need to poll all accounts on mount.
  const handleWizardComplete = async (wizardData: AccountCreationData) => {
    // Validate input data
    const validationError = validateAccountCreation(wizardData, currentOrgId);
    if (validationError) {
      toast({
        title: "Error",
        description: validationError,
        variant: "destructive",
      });
      return;
    }

    try {
      // Generate account ID upfront for progress tracking
      const newAccountId = generateAccountId();

      // Start tracking progress immediately
      console.log(
        "[AccountsManagement] Setting creatingAccountId to:",
        newAccountId,
      );
      setCreatingAccountId(newAccountId);

      // Add to accounts in setup
      setAccountsInSetup((prev) => new Set(prev).add(newAccountId));

      // Start loading operation with clear messaging
      startOperation(
        "Creating account...",
        "Conducting research on your business to configure your account. This may take 15-20 minutes.",
      );

      // Transform and create account with pre-generated ID
      const accountData = {
        ...transformWizardData(wizardData, currentOrgId!),
        accountId: newAccountId, // Include the pre-generated ID
      };
      const result = await createAccountMutation.mutateAsync(accountData);

      // Schedule consistency check after a brief delay for data propagation
      setTimeout(async () => {
        try {
          // Basic validation: check if expected data was saved
          const hasExpectedChannels =
            wizardData.marketing_channels?.length > 0
              ? result.marketing_channels?.length ===
                wizardData.marketing_channels.length
              : true;
          const hasExpectedIntegrations =
            wizardData.product_integrations?.length > 0
              ? result.product_integrations?.length ===
                wizardData.product_integrations.length
              : true;
          const hasExpectedWebsites =
            wizardData.websites?.length > 0
              ? result.websites?.length === wizardData.websites.length
              : true;

          if (
            !hasExpectedChannels ||
            !hasExpectedIntegrations ||
            !hasExpectedWebsites
          ) {
            console.warn(
              "[AccountsManagement] Account created but some expected data may be missing",
            );
            // Don't show toast here - wait for strategy completion
          }
        } catch (error) {
          console.error(
            "[AccountsManagement] Error during consistency check:",
            error,
          );
        }
      }, 2000);

      // Don't show success message yet - wait for completion
      // The progress tracking will show the success when strategy generation is done

      // Don't refresh queries here - wait for completion to avoid rate limiting
      // Just update the local context with the new account
      updateContextsAfterCreation(result, currentOrgId!);

      // Close wizard but keep the loading overlay open
      setIsCreateAccountModalOpen(false);

      // Check if Google Analytics was selected and needs OAuth setup
      if (wizardData.product_integrations?.includes("google_analytics")) {
        console.log(
          "[AccountsManagement] Google Analytics selected, initiating OAuth flow for account:",
          result.account_id,
        );

        // Trigger OAuth flow for the newly created account
        try {
          const response = await api.get(
            `/api/oauth/authorize/google-analytics?account_id=${result.account_id}`,
          );

          // Redirect to Google OAuth
          window.location.href = response.data.auth_url;
        } catch (error) {
          console.error(
            "[AccountsManagement] Failed to initiate OAuth:",
            error,
          );
          toast({
            title: "OAuth Setup",
            description:
              "Account created successfully. You can set up Google Analytics later in Account Settings.",
          });
        }
      }

      // Don't call endOperation here - let the progress tracking handle it
      console.log(
        "[AccountsManagement] Wizard account created, waiting for strategy generation to complete...",
      );
    } catch (error: unknown) {
      console.error("[AccountsManagement] Error creating account:", error);

      const errorMessage =
        axios.isAxiosError(error) && error.response?.data?.message
          ? error.response.data.message
          : "Failed to create account. Please try again.";

      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });

      // Only end operation on error
      endOperation();
      setCreatingAccountId(null);
    }
  };
  // organizationAccounts is already synced with accounts through useMemo
  // No need for a separate useEffect to update it

  // Open create account modal if requested via prop and user has admin access
  useEffect(() => {
    if (openCreateModal && !orgData.agency && hasAdminAccess) {
      setIsCreateAccountModalOpen(true);
    }
  }, [openCreateModal, orgData.agency, hasAdminAccess]);
  return (
    <TooltipProvider>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Store className="h-5 w-5" />
              Accounts
            </div>
            {!orgData.agency && hasAdminAccess && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsCreateAccountModalOpen(true)}
                className="h-8 w-8 p-0"
                disabled={isOperationInProgress}
              >
                <Plus className="h-4 w-4" />
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {orgData.agency && (
            <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Agency organizations cannot create accounts.
            </div>
          )}
          {isLoadingAccounts ? (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              <p>Loading accounts...</p>
            </div>
          ) : organizationAccounts.length > 0 ? (
            organizationAccounts.map((account) => {
              const isInSetup = accountsInSetup.has(account.account_id);
              return (
                <div
                  key={account.account_id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-[var(--color-bg-secondary)] transition-colors relative"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-brand-light-blue/20 rounded-full flex items-center justify-center">
                      <User className="h-4 w-4 text-brand-medium-blue" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-[var(--color-text-primary)]">
                          {account.account_name}
                        </h4>
                        {isInSetup && (
                          <div className="flex items-center gap-1.5 text-amber-600">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            <span className="text-xs font-medium">
                              Setting up...
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {getIndustryDisplayName(account.industry)}
                        </Badge>
                        <Badge
                          variant={
                            account.status === "Active"
                              ? "secondary"
                              : "outline"
                          }
                          className="text-xs"
                        >
                          {account.status}
                        </Badge>
                        {isInSetup && (
                          <Badge
                            variant="outline"
                            className="text-xs border-amber-200 bg-amber-50 text-amber-700"
                          >
                            Strategy generation in progress (15-20 min)
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {isInSetup && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="text-amber-600 mr-2">
                            <Info className="h-4 w-4" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="left" className="max-w-xs">
                          <p className="text-sm">
                            Your account is being configured with personalized
                            business strategies. This process typically takes
                            15-20 minutes. You can use other features while this
                            completes in the background.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {hasAdminAccess && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          navigate(`/settings/account/${account.account_id}`)
                        }
                        className="h-8 w-8 p-0"
                        disabled={isOperationInProgress}
                      >
                        <Settings className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              <User className="h-12 w-12 mx-auto mb-4 text-[var(--color-text-disabled)]" />
              <p>No accounts found for this organization</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Account Creation Wizard */}
      <AccountCreationWizard
        isOpen={isCreateAccountModalOpen}
        onClose={() => {
          setIsCreateAccountModalOpen(false);
          // Only clean up if user is canceling (not if account creation is in progress)
          // The progress tracking will clean up when creation completes/fails
          if (!creatingAccountId) {
            // No account creation in progress - safe to clean up
            if (isOperationInProgress) {
              endOperation();
            }
          }
          // Don't clear creatingAccountId here - let the progress tracking handle it
          // This allows polling to continue after wizard closes
        }}
        onComplete={handleWizardComplete}
      />
    </TooltipProvider>
  );
};

export default AccountsManagement;
