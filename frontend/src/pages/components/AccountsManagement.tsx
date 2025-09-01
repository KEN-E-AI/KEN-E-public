import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import { useToast } from "@/hooks/use-toast";
import {
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
  useInvalidateAccounts,
  accountKeys,
} from "@/queries/accounts";
import { useAccountConsistency } from "@/hooks/useAccountConsistency";
import { useAccountCreationProgress } from "@/hooks/useAccountCreationProgress";
import { useQueryClient } from "@tanstack/react-query";
import { generateAccountId } from "@/lib/idGenerator";
import { useSyncHolidayActivityLogs } from "@/queries/activities";
import type { HolidaySyncError } from "@/types/activities";
import type { AxiosError } from "axios";
import { moveAccount, getOrganizations, getOrganizationById } from "@/data/organizationApi";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { IndustrySelectDropdown as IndustrySelect } from "@/components/ui/industry-select-dropdown";
import { Textarea } from "@/components/ui/textarea";
import { MarketingChannelsSelector } from "@/components/ui/MarketingChannelsSelector";
import { MARKETING_CHANNELS } from "@/data/marketingChannels";
import {
  MARKETING_CHANNELS_WITH_DESCRIPTIONS,
  MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS,
  getChannelInfoByName,
} from "@/data/marketingChannelsWithDescriptions";
import { ProductIntegrationsSelector } from "@/components/ui/ProductIntegrationsSelector";
import { ProductIntegrationsEditor } from "@/components/ui/ProductIntegrationsEditor";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  User,
  Plus,
  X,
  Settings,
  Store,
  AlertTriangle,
  MoveRight,
  Info,
  DollarSign,
  Search,
} from "lucide-react";
import {
  INDUSTRY_OPTIONS,
  TIMEZONE_OPTIONS,
  type Organization,
  type Account,
} from "@/data/organizationTypes";
import {
  migrateIndustryValue,
  getIndustryDisplayName,
} from "@/lib/industryMigration";
import {
  migrateDataRegionValue,
  getDataRegionDisplayName,
} from "@/lib/dataRegionMigration";
import {
  AccountCreationWizard,
  type AccountCreationData,
} from "@/components/settings/AccountCreationWizard";

const REGION_OPTIONS = [
  { value: "Global", label: "Global" },
  { value: "NA", label: "NA: North America" },
  { value: "JAPAC", label: "JAPAC: Japan and Asia Pacific" },
  { value: "EMEA", label: "EMEA: Europe, the Middle East and Africa" },
  { value: "LAC", label: "LAC: Latin America and the Caribbean" },
  { value: "AE", label: "AE: United Arab Emirates" },
  { value: "AR", label: "AR: Argentina" },
  { value: "AT", label: "AT: Austria" },
  { value: "AU", label: "AU: Australia" },
  { value: "BE", label: "BE: Belgium" },
  { value: "BR", label: "BR: Brazil" },
  { value: "CA", label: "CA: Canada" },
  { value: "CH", label: "CH: Switzerland" },
  { value: "CL", label: "CL: Chile" },
  { value: "CN", label: "CN: China" },
  { value: "CO", label: "CO: Colombia" },
  { value: "CZ", label: "CZ: Czechia" },
  { value: "DE", label: "DE: Germany" },
  { value: "DK", label: "DK: Denmark" },
  { value: "DZ", label: "DZ: Algeria" },
  { value: "EC", label: "EC: Ecuador" },
  { value: "EE", label: "EE: Estonia" },
  { value: "EG", label: "EG: Egypt" },
  { value: "ES", label: "ES: Spain" },
  { value: "FI", label: "FI: Finland" },
  { value: "FR", label: "FR: France" },
  { value: "GB", label: "GB: United Kingdom" },
  { value: "GR", label: "GR: Greece" },
  { value: "HK", label: "HK: Hong Kong" },
  { value: "HU", label: "HU: Hungary" },
  { value: "ID", label: "ID: Indonesia" },
  { value: "IE", label: "IE: Ireland" },
  { value: "IL", label: "IL: Israel" },
  { value: "IN", label: "IN: India" },
  { value: "IR", label: "IR: Iran" },
  { value: "IT", label: "IT: Italy" },
  { value: "JP", label: "JP: Japan" },
  { value: "KR", label: "KR: South Korea" },
  { value: "LV", label: "LV: Latvia" },
  { value: "MA", label: "MA: Morocco" },
  { value: "MX", label: "MX: Mexico" },
  { value: "MY", label: "MY: Malaysia" },
  { value: "NG", label: "NG: Nigeria" },
  { value: "NL", label: "NL: Netherlands" },
  { value: "NO", label: "NO: Norway" },
  { value: "NZ", label: "NZ: New Zealand" },
  { value: "PE", label: "PE: Peru" },
  { value: "PH", label: "PH: Philippines" },
  { value: "PK", label: "PK: Pakistan" },
  { value: "PL", label: "PL: Poland" },
  { value: "PT", label: "PT: Portugal" },
  { value: "RO", label: "RO: Romania" },
  { value: "RS", label: "RS: Serbia" },
  { value: "RU", label: "RU: Russia" },
  { value: "SA", label: "SA: Saudi Arabia" },
  { value: "SE", label: "SE: Sweden" },
  { value: "SG", label: "SG: Singapore" },
  { value: "SI", label: "SI: Slovenia" },
  { value: "SK", label: "SK: Slovakia" },
  { value: "TH", label: "TH: Thailand" },
  { value: "TR", label: "TR: Turkey" },
  { value: "TW", label: "TW: Taiwan" },
  { value: "UA", label: "UA: Ukraine" },
  { value: "US", label: "US: United States" },
  { value: "VE", label: "VE: Venezuela" },
  { value: "VN", label: "VN: Vietnam" },
  { value: "ZA", label: "ZA: South Africa" },
];

interface AccountsManagementProps {
  orgData: Organization;
  currentOrgId: string;
  openCreateModal?: boolean;
  hasAdminAccess?: boolean;
}

const AccountsManagement = ({
  orgData,
  currentOrgId,
  openCreateModal = false,
  hasAdminAccess = true,
}: AccountsManagementProps) => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const {
    accountMetadata,
    setAccountMetadata,
    user,
    updateUser,
    orgMetadata,
    setOrgMetadata,
    selectedOrgAccount,
    setSelectedOrgAccount,
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
  const queryClient = useQueryClient();
  const { data: accounts = [], isLoading: isLoadingAccounts } =
    useAccounts(currentOrgId);
  const createAccountMutation = useCreateAccount();
  const deleteAccountMutation = useDeleteAccount();
  const updateAccountMutation = useUpdateAccount();
  const syncHolidayMutation = useSyncHolidayActivityLogs();
  const invalidateAccounts = useInvalidateAccounts();

  // State for tracking account creation
  const [creatingAccountId, setCreatingAccountId] = useState<string | null>(
    null,
  );

  // Hook for tracking account creation progress
  const accountCreationProgress = useAccountCreationProgress(creatingAccountId);

  // Update the operation message when progress changes (simplified)
  useEffect(() => {
    if (accountCreationProgress && accountCreationProgress.status !== "idle") {
      console.log("[AccountsManagement] Progress update received:", accountCreationProgress);
      
      // Update the operation message based on status
      if (accountCreationProgress.status === "processing") {
        updateOperationMessage("Creating account...", accountCreationProgress.message);
      }
      
      // Check if account creation is complete
      if (accountCreationProgress.status === "completed") {
        console.log("[AccountsManagement] Account creation complete! Refreshing data...");
        
        // Show success toast
        toast({
          title: "Success",
          description: "Account created successfully with all strategy documents!",
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
            
            console.log("[AccountsManagement] Cache invalidated successfully after account creation");
          } catch (error) {
            console.error("[AccountsManagement] Error refreshing data after account creation:", error);
          } finally {
            // Always end the operation and clear the tracking ID
            endOperation();
            setCreatingAccountId(null);
          }
        }, 2000); // 2 second delay to show completion
      }
      
      // Handle failure
      if (accountCreationProgress.status === "failed") {
        console.error("[AccountsManagement] Account creation failed");
        toast({
          title: "Error",
          description: accountCreationProgress.message || "Account creation failed. Please try again.",
          variant: "destructive",
        });
        endOperation();
        setCreatingAccountId(null);
      }
    }
  }, [accountCreationProgress, updateOperationMessage, endOperation, toast, currentOrgId, setOrgMetadata, refreshNotifications]);

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

  const transformWizardData = (data: AccountCreationData, orgId: string) => ({
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
  });

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


  // State for account management
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCreateAccountModalOpen, setIsCreateAccountModalOpen] =
    useState(false);
  const [isEditRegionPopoverOpen, setIsEditRegionPopoverOpen] = useState(false);
  const [
    isEditMarketingChannelsPopoverOpen,
    setIsEditMarketingChannelsPopoverOpen,
  ] = useState(false);
  const [marketingChannelSearchTerm, setMarketingChannelSearchTerm] =
    useState("");
  const [isCreateRegionPopoverOpen, setIsCreateRegionPopoverOpen] =
    useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  // State for move account functionality
  const [isMoveAccountDialogOpen, setIsMoveAccountDialogOpen] = useState(false);
  const [targetOrganizationId, setTargetOrganizationId] = useState("");
  const [availableOrganizations, setAvailableOrganizations] = useState<
    Organization[]
  >([]);
  const [isLoadingOrganizations, setIsLoadingOrganizations] = useState(false);

  // Refs for click-outside handling
  const editRegionDropdownRef = useRef<HTMLDivElement>(null);
  const editMarketingChannelsDropdownRef = useRef<HTMLDivElement>(null);
  const createRegionDropdownRef = useRef<HTMLDivElement>(null);

  // Handle click outside to close dropdowns
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        editRegionDropdownRef.current &&
        !editRegionDropdownRef.current.contains(event.target as Node)
      ) {
        setIsEditRegionPopoverOpen(false);
      }
      if (
        editMarketingChannelsDropdownRef.current &&
        !editMarketingChannelsDropdownRef.current.contains(event.target as Node)
      ) {
        setIsEditMarketingChannelsPopoverOpen(false);
        setMarketingChannelSearchTerm("");
      }
      if (
        createRegionDropdownRef.current &&
        !createRegionDropdownRef.current.contains(event.target as Node)
      ) {
        setIsCreateRegionPopoverOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const [editFormData, setEditFormData] = useState({
    account_name: "",
    description: "",
    industry: "",
    status: "",
    websites: [""],
    estimated_annual_ad_budget: null as number | null,
    marketing_channels: [] as string[],
    product_integrations: [] as string[],
    timezone: "",
    data_region: "",
    region: [] as string[],
  });

  const [createAccountFormData, setCreateAccountFormData] = useState({
    account_name: "",
    industry: "",
    status: "Active",
    websites: [""],
    timezone: "America/New_York",
    data_region: "US",
    region: ["US"] as string[],
    estimated_annual_ad_budget: null as number | null,
    business_strategy_documents: [] as File[],
  });

  // Filter accounts based on user permissions
  const organizationAccounts = useMemo(() => {
    // Super admins or organization admins have access to all accounts
    if (isSuperAdmin || hasAdminAccess) {
      return accounts;
    }

    // Regular users only see accounts they have explicit permissions for
    return accounts.filter((account) => {
      return user?.permissions?.accounts?.[account.account_id];
    });
  }, [accounts, user?.permissions?.accounts, isSuperAdmin, hasAdminAccess]);

  // Region management helpers
  const toggleRegion = (regionValue: string, isEdit: boolean = true) => {
    const formData = isEdit ? editFormData : createAccountFormData;
    const setFormData = isEdit ? setEditFormData : setCreateAccountFormData;

    const currentRegions = formData.region;
    const newRegions = currentRegions.includes(regionValue)
      ? currentRegions.filter((r) => r !== regionValue)
      : [...currentRegions, regionValue];

    setFormData({
      ...formData,
      region: newRegions,
    });
  };

  // Marketing channels management helpers
  const toggleMarketingChannel = (channel: string) => {
    const currentChannels = editFormData.marketing_channels;
    const newChannels = currentChannels.includes(channel)
      ? currentChannels.filter((c) => c !== channel)
      : [...currentChannels, channel];

    setEditFormData({
      ...editFormData,
      marketing_channels: newChannels,
    });
  };

  const getSelectedRegionLabels = (regions: string[]) => {
    return regions
      .map((regionValue) => {
        const option = REGION_OPTIONS.find((opt) => opt.value === regionValue);
        return option ? option.label : regionValue;
      })
      .join(", ");
  };

  // Event handlers
  const handleEditAccount = (account: Account) => {
    if (isOperationInProgress) return;

    // Debug logging to see what data we're receiving
    console.log("[AccountsManagement] Editing account:", account);
    console.log(
      "[AccountsManagement] Account marketing_channels:",
      account.marketing_channels,
    );
    console.log(
      "[AccountsManagement] Account product_integrations:",
      account.product_integrations,
    );

    setSelectedAccount(account);
    const existingRegion = account.region;
    let regionArray: string[] = [];

    if (Array.isArray(existingRegion)) {
      regionArray = existingRegion;
    } else if (typeof existingRegion === "string" && existingRegion) {
      regionArray = [existingRegion];
    }

    // Migrate industry value if needed
    const migratedIndustry = migrateIndustryValue(account.industry);

    // Migrate data_region value if needed
    const migratedDataRegion = migrateDataRegionValue(account.data_region);

    const formData = {
      account_name: account.account_name,
      description: account.description || "",
      industry: migratedIndustry,
      status: account.status,
      websites:
        account.websites && account.websites.length > 0
          ? account.websites
          : [""],
      estimated_annual_ad_budget: account.estimated_annual_ad_budget || null,
      marketing_channels: account.marketing_channels || [],
      product_integrations: account.product_integrations || [],
      timezone: account.timezone || "America/New_York",
      data_region: migratedDataRegion,
      region: regionArray,
    };

    console.log("[AccountsManagement] Setting editFormData to:", formData);
    setEditFormData(formData);
    setIsModalOpen(true);
  };

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

      // Update account in Neo4j (source of truth)
      const updatedAccount = await updateAccountMutation.mutateAsync({
        accountId: selectedAccount.account_id,
        updates: {
          account_name: editFormData.account_name,
          description: editFormData.description,
          industry: editFormData.industry,
          status: editFormData.status,
          websites: editFormData.websites,
          estimated_annual_ad_budget: editFormData.estimated_annual_ad_budget,
          marketing_channels: editFormData.marketing_channels,
          product_integrations: editFormData.product_integrations,
          timezone: editFormData.timezone,
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

          // Check for partial success
          if (syncResult.data.errors && syncResult.data.errors.length > 0) {
            toast({
              title: "Partial Sync",
              description: `Holiday activities synced with ${syncResult.data.errors.length} warnings. ${syncResult.data.new_logs_created} created, ${syncResult.data.logs_deleted} deleted.`,
              variant: "default",
            });
          } else {
            toast({
              title: "Holiday Activities Synced",
              description: `Updated ${syncResult.data.new_logs_created} holidays for ${syncResult.data.regions.join(", ")}.`,
            });
          }
        } catch (error) {
          const syncError = error as AxiosError<HolidaySyncError>;
          console.error("Error syncing holiday activities:", syncError);

          const errorMessage =
            syncError.response?.data?.message ||
            "Holiday sync failed. You may need to sync manually.";

          toast({
            title: "Sync Warning",
            description: `Account updated successfully. ${errorMessage}`,
            variant: "destructive",
          });
        }
      }

      // Update contexts
      updateOperationMessage("Finalizing update...", "Refreshing data");

      // Update local accountMetadata context
      setAccountMetadata((prev) => ({
        ...prev,
        [selectedAccount.account_id]: updatedAccount,
      }));

      // Update organization metadata to reflect the change
      setOrgMetadata((prev) => ({
        ...prev,
        [currentOrgId]: {
          ...prev[currentOrgId],
          accounts:
            prev[currentOrgId]?.accounts?.map((acc) =>
              acc.account_id === selectedAccount.account_id
                ? updatedAccount
                : acc,
            ) || [],
        },
      }));

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
      console.log("[AccountsManagement] Setting creatingAccountId to:", newAccountId);
      setCreatingAccountId(newAccountId);
      
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
      
      // Don't call endOperation here - let the progress tracking handle it
      console.log("[AccountsManagement] Wizard account created, waiting for strategy generation to complete...");
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

  const handleCreateAccount = async () => {
    console.log("[AccountsManagement] handleCreateAccount called");
    console.log("[AccountsManagement] Current org ID:", currentOrgId);
    console.log("[AccountsManagement] Form data:", createAccountFormData);

    if (!currentOrgId) {
      toast({
        title: "Error",
        description:
          "No organization selected. Please select an organization first.",
        variant: "destructive",
      });
      return;
    }

    if (
      !createAccountFormData.account_name ||
      !createAccountFormData.industry
    ) {
      toast({
        title: "Validation Error",
        description: "Please fill in required fields",
        variant: "destructive",
      });
      return;
    }

    try {
      // Start the loading overlay
      // Generate account ID upfront for progress tracking
      const newAccountId = generateAccountId();
      
      // Start tracking progress immediately
      console.log("[AccountsManagement] Setting creatingAccountId to:", newAccountId);
      setCreatingAccountId(newAccountId);
      
      startOperation(
        "Creating account...",
        "Conducting research on your business to configure your account. This may take 15-20 minutes.",
      );

      // Close the modal immediately to prevent duplicate clicks
      setIsCreateAccountModalOpen(false);

      // Create account in Neo4j (source of truth) with pre-generated ID
      const newAccount = await createAccountMutation.mutateAsync({
        accountId: newAccountId,
        accountName: createAccountFormData.account_name,
        organizationId: currentOrgId,
        industry: createAccountFormData.industry,
        status: createAccountFormData.status,
        websites: createAccountFormData.websites,
        timezone: createAccountFormData.timezone,
        dataRegion: createAccountFormData.data_region,
        region: createAccountFormData.region,
        estimatedAnnualAdBudget:
          createAccountFormData.estimated_annual_ad_budget,
        businessStrategyDocuments:
          createAccountFormData.business_strategy_documents,
      });

      console.log(
        "[AccountsManagement] Account created successfully:",
        newAccount,
      );

      // Update loading message (progress will be handled by the hook)
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
          console.log(
            "[AccountsManagement] Holiday activities synced for new account",
          );
        } catch (syncError) {
          console.error(
            "Error syncing holiday activities for new account:",
            syncError,
          );
          // Don't block account creation due to sync failure
        }
      }

      // Update loading message
      updateOperationMessage("Finalizing setup...", "Updating permissions");

      // Get user's permission level for the organization to apply same level to new account
      console.log("[AccountsManagement] User object:", user);
      console.log("[AccountsManagement] User permissions:", user?.permissions);
      const userOrgPermission =
        user?.permissions?.organizations?.[currentOrgId] || "view";
      console.log(
        "[AccountsManagement] User org permission:",
        userOrgPermission,
      );

      // Add the new account to user's permissions with same level as organization
      console.log("[AccountsManagement] Updating Firestore permissions...");

      let firestoreUpdateFailed = false;

      // Skip Firestore update if no user ID
      if (!user?.id) {
        console.warn(
          "[AccountsManagement] No user ID, skipping Firestore permission update",
        );
        firestoreUpdateFailed = true;
      } else {
        const firestoreUrl = `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/users/${user.id}?account_id=${user.id}`;
        console.log("[AccountsManagement] Firestore URL:", firestoreUrl);

        try {
          await axios.put(firestoreUrl, {
            update: {
              // This is a nested field path for dot-notation update
              field: `permissions.accounts.${newAccountId}`,
              operator: "set",
              value: userOrgPermission,
            },
          });
          console.log(
            "[AccountsManagement] Firestore permissions updated successfully",
          );
        } catch (firestoreError: any) {
          console.error(
            "[AccountsManagement] Firestore update error:",
            firestoreError,
          );
          console.error(
            "[AccountsManagement] Firestore error response:",
            firestoreError.response?.data,
          );
          // Continue even if Firestore update fails - account was created in Neo4j
          console.warn(
            "[AccountsManagement] Continuing despite Firestore error - account was created in Neo4j",
          );
          firestoreUpdateFailed = true;
        }
      }

      // 🧠 Update local context
      setAccountMetadata({
        ...accountMetadata,
        [newAccountId]: newAccount,
      });

      // Update user's local permissions state
      updateUser({
        permissions: {
          ...user?.permissions,
          accounts: {
            ...user?.permissions?.accounts,
            [newAccountId]: userOrgPermission,
          },
        },
      });

      // Update orgMetadata to include the new account
      setOrgMetadata((prev) => ({
        ...prev,
        [currentOrgId]: {
          ...prev[currentOrgId],
          accounts: [...(prev[currentOrgId]?.accounts || []), newAccount],
        },
      }));

      setIsCreateAccountModalOpen(false);
      setCreateAccountFormData({
        account_name: "",
        industry: "",
        status: "Active",
        websites: [""],
        timezone: "America/New_York",
        data_region: "US",
        region: ["US"],
      });

      // Set the newly created account as selected in auth context
      console.log(
        "[AccountsManagement] Setting selected account and redirecting...",
      );

      // Update auth context with the new selected account
      const selectedOrgAccount = {
        orgId: currentOrgId,
        accountId: newAccountId,
        metadata: {
          organization_name: orgData.organization_name,
          account_name: newAccount.account_name,
          industry: newAccount.industry,
          status: newAccount.status,
          timezone: newAccount.timezone,
          plan: orgData.plan,
        },
      };

      // Set the selected account in auth context
      setSelectedOrgAccount(selectedOrgAccount);

      // Don't end operation or navigate yet - wait for progress to complete
      // The progress tracking will handle closing the modal and navigation
      console.log("[AccountsManagement] Account created, waiting for strategy generation to complete...");
    } catch (error: any) {
      // Make sure to end the loading state on error
      endOperation();
      setCreatingAccountId(null);

      console.error("[AccountsManagement] Error creating account:", error);
      console.error("[AccountsManagement] Error details:", {
        message: error.message,
        response: error.response,
        stack: error.stack,
      });

      // Show more detailed error message
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

  // organizationAccounts is already synced with accounts through useMemo
  // No need for a separate useEffect to update it

  // Open create account modal if requested via prop and user has admin access
  useEffect(() => {
    if (openCreateModal && !orgData.agency && hasAdminAccess) {
      setIsCreateAccountModalOpen(true);
    }
  }, [openCreateModal, orgData.agency, hasAdminAccess]);

  // Fetch organizations when move dialog opens
  useEffect(() => {
    if (isMoveAccountDialogOpen) {
      const fetchOrganizations = async () => {
        setIsLoadingOrganizations(true);
        try {
          const orgs = await getOrganizations();
          // Filter out current organization and only show orgs where user has admin/owner permissions
          const filteredOrgs = orgs.filter(
            (org) =>
              org.organization_id !== currentOrgId &&
              (user?.permissions?.organizations?.[org.organization_id] ===
                "admin" ||
                user?.permissions?.organizations?.[org.organization_id] ===
                  "owner"),
          );
          setAvailableOrganizations(filteredOrgs);
        } catch (error) {
          console.error(
            "[AccountsManagement] Error fetching organizations:",
            error,
          );
          toast({
            title: "Error",
            description: "Failed to load organizations. Please try again.",
            variant: "destructive",
          });
        } finally {
          setIsLoadingOrganizations(false);
        }
      };
      fetchOrganizations();
    }
  }, [
    isMoveAccountDialogOpen,
    currentOrgId,
    user?.permissions?.organizations,
    toast,
  ]);

  const handleMoveAccount = async () => {
    if (!selectedAccount || !targetOrganizationId) {
      toast({
        title: "Error",
        description: "Please select a destination organization",
        variant: "destructive",
      });
      return;
    }

    const targetOrg = availableOrganizations.find(
      (org) => org.organization_id === targetOrganizationId,
    );

    if (!targetOrg) {
      toast({
        title: "Error",
        description: "Invalid organization selected",
        variant: "destructive",
      });
      return;
    }

    // Show confirmation toast
    toast({
      title: "Confirm Move",
      description: `Are you sure you want to move "${selectedAccount.account_name}" to "${targetOrg.organization_name}"?`,
      action: (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // User cancelled - just close the toast
            }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={async () => {
              try {
                // Start loading overlay
                startOperation(
                  "Moving account...",
                  `Transferring "${selectedAccount.account_name}" to "${targetOrg.organization_name}"`,
                );

                // Close dialogs
                setIsMoveAccountDialogOpen(false);
                setIsModalOpen(false);

                console.log(
                  "[AccountsManagement] Moving account:",
                  selectedAccount.account_id,
                  "to organization:",
                  targetOrganizationId,
                );

                // Call the move API
                await moveAccount(
                  currentOrgId,
                  selectedAccount.account_id,
                  targetOrganizationId,
                );

                // organizationAccounts will automatically update when accounts query is refetched
                // No need to manually update it since it's computed from accounts data

                // Remove from account metadata
                const newAccountMetadata = { ...accountMetadata };
                delete newAccountMetadata[selectedAccount.account_id];
                setAccountMetadata(newAccountMetadata);

                // Update org metadata to remove account from current org
                setOrgMetadata((prev) => ({
                  ...prev,
                  [currentOrgId]: {
                    ...prev[currentOrgId],
                    accounts:
                      prev[currentOrgId]?.accounts?.filter(
                        (acc) => acc.account_id !== selectedAccount.account_id,
                      ) || [],
                  },
                }));

                // Clear state
                setSelectedAccount(null);
                setTargetOrganizationId("");

                endOperation();

                toast({
                  title: "Account Moved",
                  description: `"${selectedAccount.account_name}" has been moved to "${targetOrg.organization_name}" successfully.`,
                });

                console.log("[AccountsManagement] Account moved successfully");
              } catch (error: any) {
                console.error(
                  "[AccountsManagement] Error moving account:",
                  error,
                );

                endOperation();

                const errorMessage =
                  error.response?.data?.detail ||
                  error.message ||
                  "Failed to move account";

                toast({
                  title: "Error",
                  description: `Error: ${errorMessage}`,
                  variant: "destructive",
                });
              }
            }}
          >
            Confirm
          </Button>
        </div>
      ),
    });
  };

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

    // Store account info before ANY state changes
    const accountId = account.account_id;
    const accountName = account.account_name;
    // Safely check if we're deleting the current account
    const currentAccountId = selectedOrgAccount?.accountId;
    const isDeletingCurrentAccount = currentAccountId
      ? accountId === currentAccountId
      : false;

    console.log("[AccountsManagement] Delete account debug:", {
      accountId,
      accountName,
      currentAccountId,
      isDeletingCurrentAccount,
      selectedOrgAccount: selectedOrgAccount ? "exists" : "null",
    });

    // Close ALL dialogs immediately to prevent UI issues
    setIsDeleteDialogOpen(false);
    setIsModalOpen(false);
    setIsEditRegionPopoverOpen(false);
    setIsCreateRegionPopoverOpen(false);
    setIsMoveAccountDialogOpen(false);

    // Clear selected account state to prevent accessing stale data
    setSelectedAccount(null);

    try {
      // Start loading overlay with specific message
      startOperation(
        "Deleting account...",
        `Removing "${accountName}" and all associated data`,
      );

      // If deleting the current account, clear auth state immediately to prevent freeze
      if (isDeletingCurrentAccount) {
        // Clear account metadata immediately
        const newAccountMetadata = { ...accountMetadata };
        delete newAccountMetadata[accountId];
        setAccountMetadata(newAccountMetadata);

        // Clear selected org account if it matches
        setSelectedOrgAccount(null);
      }

      await deleteAccountMutation.mutateAsync({
        orgId: currentOrgId!,
        accountId: accountId,
      });

      // End loading state
      endOperation();

      // Show success message
      toast({
        title: "Account Deleted",
        description: `"${accountName}" and all related entities have been permanently deleted.`,
      });

      // Update organization metadata to remove the deleted account
      if (!isDeletingCurrentAccount) {
        // Remove from account metadata
        const newAccountMetadata = { ...accountMetadata };
        delete newAccountMetadata[accountId];
        setAccountMetadata(newAccountMetadata);

        // Update org metadata to remove the account
        setOrgMetadata((prev) => ({
          ...prev,
          [currentOrgId]: {
            ...prev[currentOrgId],
            accounts:
              prev[currentOrgId]?.accounts?.filter(
                (acc: any) => acc.account_id !== accountId,
              ) || [],
          },
        }));
      }

      // If we deleted the current account, clear the selected account but stay on organization settings
      if (isDeletingCurrentAccount) {
        // Clear the selected account in auth context since it no longer exists
        setSelectedOrgAccount(null);
        // Stay on the current page - user can create new accounts from here
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

  // Website field management
  const addWebsiteField = () => {
    setEditFormData({
      ...editFormData,
      websites: [...editFormData.websites, ""],
    });
  };

  const removeWebsiteField = (index: number) => {
    const newWebsites = editFormData.websites.filter((_, i) => i !== index);
    setEditFormData({
      ...editFormData,
      websites: newWebsites.length > 0 ? newWebsites : [""],
    });
  };

  const updateWebsiteField = (index: number, value: string) => {
    const newWebsites = [...editFormData.websites];
    newWebsites[index] = value;
    setEditFormData({
      ...editFormData,
      websites: newWebsites,
    });
  };

  // Create account website management
  const addCreateWebsiteField = () => {
    setCreateAccountFormData({
      ...createAccountFormData,
      websites: [...createAccountFormData.websites, ""],
    });
  };

  const removeCreateWebsiteField = (index: number) => {
    const newWebsites = createAccountFormData.websites.filter(
      (_, i) => i !== index,
    );
    setCreateAccountFormData({
      ...createAccountFormData,
      websites: newWebsites.length > 0 ? newWebsites : [""],
    });
  };

  const updateCreateWebsiteField = (index: number, value: string) => {
    const newWebsites = [...createAccountFormData.websites];
    newWebsites[index] = value;
    setCreateAccountFormData({
      ...createAccountFormData,
      websites: newWebsites,
    });
  };

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
            <div className="text-center py-8 text-gray-500">
              <p>Loading accounts...</p>
            </div>
          ) : organizationAccounts.length > 0 ? (
            organizationAccounts.map((account) => (
              <div
                key={account.account_id}
                className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-brand-light-blue/20 rounded-full flex items-center justify-center">
                    <User className="h-4 w-4 text-brand-medium-blue" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900">
                      {account.account_name}
                    </h4>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className="text-xs">
                        {getIndustryDisplayName(account.industry)}
                      </Badge>
                      <Badge
                        variant={
                          account.status === "Active" ? "secondary" : "outline"
                        }
                        className="text-xs"
                      >
                        {account.status}
                      </Badge>
                    </div>
                  </div>
                </div>
                {hasAdminAccess && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEditAccount(account)}
                    className="h-8 w-8 p-0"
                    disabled={isOperationInProgress}
                  >
                    <Settings className="h-4 w-4 text-gray-500" />
                  </Button>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-gray-500">
              <User className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No accounts found for this organization</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Account Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Account</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="account-name">Account Name</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      A friendly name for the account. If you have different
                      types of customers who each require a unique strategy, you
                      should consider creating multiple accounts (example:
                      Company B2B, and Company B2C).
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                id="account-name"
                value={editFormData.account_name}
                onChange={(e) =>
                  setEditFormData({
                    ...editFormData,
                    account_name: e.target.value,
                  })
                }
                placeholder="Enter account name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-industry">Industry</Label>
              <IndustrySelect
                value={editFormData.industry}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    industry: value,
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-description">Description</Label>
              <Textarea
                id="account-description"
                value={editFormData.description}
                onChange={(e) =>
                  setEditFormData({
                    ...editFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Brief description of this account..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="edit-budget">
                  <DollarSign className="inline h-4 w-4 mr-1" />
                  Estimated Annual Ad Budget (USD)
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      This helps KEN-E provide better budget optimization
                      recommendations
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                id="edit-budget"
                type="number"
                min="0"
                step="1000"
                value={editFormData.estimated_annual_ad_budget || ""}
                onChange={(e) => {
                  const value = e.target.value;
                  setEditFormData({
                    ...editFormData,
                    estimated_annual_ad_budget: value
                      ? parseInt(value, 10)
                      : null,
                  });
                }}
                placeholder="e.g., 100000"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="account-status">Status</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      Set the status to inactive to temporarily pause all data
                      processing and charges.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Select
                value={editFormData.status}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    status: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Active">Active</SelectItem>
                  <SelectItem value="Inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="account-timezone">Timezone</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      Set the timezone to the same value selected in your
                      martech platforms to ensure all data is aligned to the
                      proper date.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Select
                value={editFormData.timezone}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    timezone: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select timezone" />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="account-data-region">Data Region</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      The location where your data is stored. Once your account
                      is created you cannot change this setting.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                value={getDataRegionDisplayName(editFormData.data_region)}
                readOnly
                className="bg-gray-50 cursor-not-allowed"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Customer Region</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent
                      className="max-w-sm text-sm"
                      side="right"
                      align="center"
                      avoidCollisions={true}
                      collisionPadding={10}
                      sideOffset={5}
                    >
                      <p>
                        Select all regions where your target customers live.
                        This will be used to understand how regional holidays
                        influence your business metrics.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="relative" ref={editRegionDropdownRef}>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() =>
                      setIsEditRegionPopoverOpen(!isEditRegionPopoverOpen)
                    }
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                  {isEditRegionPopoverOpen && (
                    <div className="absolute top-full right-0 mt-1 w-80 bg-white border border-gray-200 rounded-md shadow-lg z-50 max-h-60 overflow-y-auto">
                      {REGION_OPTIONS.map((option) => (
                        <div
                          key={option.value}
                          className="flex items-center space-x-2 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
                          onClick={() => {
                            if (!editFormData.region.includes(option.value)) {
                              toggleRegion(option.value, true);
                              setIsEditRegionPopoverOpen(false);
                            }
                          }}
                        >
                          <span className="flex-1">{option.label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                {editFormData.region.map((regionValue, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={
                        REGION_OPTIONS.find((opt) => opt.value === regionValue)
                          ?.label || regionValue
                      }
                      readOnly
                      className="flex-1 bg-gray-50"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => toggleRegion(regionValue, true)}
                      className="h-10 w-10 p-0 text-red-500 hover:text-red-700"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Websites</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent
                      className="max-w-sm text-sm"
                      side="right"
                      align="center"
                      avoidCollisions={true}
                      collisionPadding={10}
                      sideOffset={5}
                    >
                      <p>
                        List all of your websites. KEN-E will study these to
                        understand your business and products/services.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addWebsiteField}
                  className="h-8 w-8 p-0"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {editFormData.websites.map((website, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={website}
                      onChange={(e) =>
                        updateWebsiteField(index, e.target.value)
                      }
                      placeholder="Enter website URL"
                      className="flex-1"
                    />
                    {editFormData.websites.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeWebsiteField(index)}
                        className="h-10 w-10 p-0 text-red-500 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Marketing Channels</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent
                      className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                      side="right"
                      align="center"
                      avoidCollisions={true}
                      collisionPadding={10}
                      sideOffset={5}
                    >
                      <p>
                        Select the marketing channels you currently use or plan
                        to use for this account to improve KEN-E's
                        recommendations.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div
                  className="relative"
                  ref={editMarketingChannelsDropdownRef}
                >
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() =>
                      setIsEditMarketingChannelsPopoverOpen(
                        !isEditMarketingChannelsPopoverOpen,
                      )
                    }
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                  {isEditMarketingChannelsPopoverOpen && (
                    <div className="absolute top-full right-0 mt-1 w-96 bg-white border border-gray-200 rounded-md shadow-lg z-50">
                      <div className="sticky top-0 bg-white border-b border-gray-200 p-2">
                        <div className="relative">
                          <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                          <Input
                            type="text"
                            placeholder="Search marketing channels..."
                            className="pl-8 pr-2 py-1 text-sm"
                            value={marketingChannelSearchTerm}
                            onChange={(e) =>
                              setMarketingChannelSearchTerm(e.target.value)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      </div>
                      <div className="max-h-80 overflow-y-auto">
                        {marketingChannelSearchTerm
                          ? // When searching, show flat list
                            MARKETING_CHANNELS_WITH_DESCRIPTIONS.filter(
                              (channel) =>
                                channel.name
                                  .toLowerCase()
                                  .includes(
                                    marketingChannelSearchTerm.toLowerCase(),
                                  ) ||
                                channel.description
                                  .toLowerCase()
                                  .includes(
                                    marketingChannelSearchTerm.toLowerCase(),
                                  ),
                            ).map((channelInfo) => {
                              const isSelected =
                                editFormData.marketing_channels.includes(
                                  channelInfo.name,
                                );
                              return (
                                <div
                                  key={channelInfo.id}
                                  className={`px-3 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0 ${
                                    isSelected
                                      ? "opacity-50 cursor-not-allowed bg-gray-50"
                                      : ""
                                  }`}
                                  onClick={() => {
                                    if (!isSelected) {
                                      toggleMarketingChannel(channelInfo.name);
                                      setIsEditMarketingChannelsPopoverOpen(
                                        false,
                                      );
                                      setMarketingChannelSearchTerm("");
                                    }
                                  }}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1">
                                      <div className="font-medium text-sm text-gray-900">
                                        {channelInfo.name}
                                      </div>
                                      <div className="text-xs text-gray-500 mt-1">
                                        {channelInfo.description}
                                      </div>
                                    </div>
                                    {isSelected && (
                                      <span className="text-xs text-gray-400 mt-1">
                                        Added
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          : // When not searching, show grouped by category
                            Object.entries(
                              MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS,
                            ).map(([category, channels]) => (
                              <div key={category}>
                                <div className="px-3 py-2 bg-gray-50 border-b border-gray-200">
                                  <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    {category}
                                  </h4>
                                </div>
                                {channels.map((channelInfo) => {
                                  const isSelected =
                                    editFormData.marketing_channels.includes(
                                      channelInfo.name,
                                    );
                                  return (
                                    <div
                                      key={channelInfo.id}
                                      className={`px-3 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0 ${
                                        isSelected
                                          ? "opacity-50 cursor-not-allowed bg-gray-50"
                                          : ""
                                      }`}
                                      onClick={() => {
                                        if (!isSelected) {
                                          toggleMarketingChannel(
                                            channelInfo.name,
                                          );
                                          setIsEditMarketingChannelsPopoverOpen(
                                            false,
                                          );
                                          setMarketingChannelSearchTerm("");
                                        }
                                      }}
                                    >
                                      <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1">
                                          <div className="font-medium text-sm text-gray-900">
                                            {channelInfo.name}
                                          </div>
                                          <div className="text-xs text-gray-500 mt-1">
                                            {channelInfo.description}
                                          </div>
                                        </div>
                                        {isSelected && (
                                          <span className="text-xs text-gray-400 mt-1">
                                            Added
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                {editFormData.marketing_channels.map((channel, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={channel}
                      readOnly
                      className="flex-1 bg-gray-50"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => toggleMarketingChannel(channel)}
                      className="h-10 w-10 p-0 text-red-500 hover:text-red-700"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                {editFormData.marketing_channels.length === 0 && (
                  <p className="text-xs text-dashboard-gray-500">
                    No marketing channels selected. Add channels using the +
                    button above.
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label>Product Integrations</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent
                    className="max-w-sm text-sm z-50 bg-white border border-gray-200 shadow-lg"
                    side="right"
                    align="center"
                    avoidCollisions={true}
                    collisionPadding={10}
                    sideOffset={5}
                  >
                    <p>
                      Select and configure the marketing tools you want to
                      integrate with KEN-E. Click the gear icon to configure
                      each integration.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <ProductIntegrationsEditor
                value={editFormData.product_integrations}
                onChange={(integrations) =>
                  setEditFormData({
                    ...editFormData,
                    product_integrations: integrations,
                  })
                }
                enabledIntegrations={editFormData.product_integrations.filter(
                  (id) => {
                    // TODO: Replace with actual enabled status from API
                    // For now, mark first 2 as enabled for demo
                    const index = editFormData.product_integrations.indexOf(id);
                    return index < 2;
                  },
                )}
                onConfigure={(integrationId) => {
                  // TODO: Open configuration dialog for the integration
                  toast({
                    title: "Configuration",
                    description: `Configure ${integrationId} integration (coming soon)`,
                  });
                }}
                compact={true}
              />
            </div>

            {/* Danger Zone */}
            <div className="pt-6">
              <div className="border border-red-200 rounded-lg p-4 bg-red-50/50">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                  <h3 className="text-sm font-medium text-red-600">
                    Danger Zone
                  </h3>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                      <Label className="text-blue-600 text-sm font-medium">
                        Move Account
                      </Label>
                      <p className="text-xs text-gray-600 mt-1">
                        Move this account to a different organization
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setIsMoveAccountDialogOpen(true);
                        setTargetOrganizationId("");
                      }}
                      className="ml-4 text-blue-600 border-blue-200 hover:bg-blue-50"
                      disabled={isOperationInProgress}
                    >
                      <MoveRight className="h-4 w-4 mr-1" />
                      Move Account
                    </Button>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                      <Label className="text-red-600 text-sm font-medium">
                        Delete Account
                      </Label>
                      <p className="text-xs text-gray-600 mt-1">
                        Permanently delete this account and all associated data
                      </p>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setIsDeleteDialogOpen(true)}
                      className="ml-4"
                      disabled={isOperationInProgress}
                    >
                      Delete Account
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => setIsModalOpen(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSaveAccount}
                className="flex-1"
                disabled={
                  updateAccountMutation.isPending || isOperationInProgress
                }
              >
                {updateAccountMutation.isPending ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Account Creation Wizard */}
      <AccountCreationWizard
        isOpen={isCreateAccountModalOpen}
        onClose={() => setIsCreateAccountModalOpen(false)}
        onComplete={handleWizardComplete}
      />

      {/* Move Account Dialog */}
      <Dialog
        open={isMoveAccountDialogOpen}
        onOpenChange={(open) => {
          setIsMoveAccountDialogOpen(open);
          if (!open) {
            setTargetOrganizationId("");
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Move Account to Another Organization</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <p className="text-sm text-gray-600">
              Select the organization you want to move "
              {selectedAccount?.account_name}" to:
            </p>

            <div className="space-y-2">
              <Label htmlFor="target-organization">
                Destination Organization
              </Label>
              <Select
                value={targetOrganizationId}
                onValueChange={setTargetOrganizationId}
                disabled={isLoadingOrganizations}
              >
                <SelectTrigger id="target-organization">
                  <SelectValue
                    placeholder={
                      isLoadingOrganizations
                        ? "Loading..."
                        : "Select an organization"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableOrganizations.length === 0 &&
                  !isLoadingOrganizations ? (
                    <div className="p-2 text-sm text-gray-500 text-center">
                      No organizations available
                    </div>
                  ) : (
                    availableOrganizations.map((org) => (
                      <SelectItem
                        key={org.organization_id}
                        value={org.organization_id}
                      >
                        <div className="flex flex-col">
                          <span>{org.organization_name}</span>
                          <span className="text-xs text-gray-500">
                            {org.plan}
                            {org.company_size ? ` • ${org.company_size}` : ""}
                          </span>
                        </div>
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {targetOrganizationId && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                <p className="text-sm text-amber-800">
                  <strong>Note:</strong> Moving this account will transfer all
                  associated data to the new organization.
                </p>
              </div>
            )}

            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsMoveAccountDialogOpen(false);
                  setTargetOrganizationId("");
                }}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleMoveAccount}
                disabled={
                  !targetOrganizationId ||
                  isLoadingOrganizations ||
                  isOperationInProgress
                }
                className="flex-1"
              >
                Move Account
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Account Confirmation Dialog */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Account</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <div>
                  Are you sure you want to delete the account{" "}
                  <strong>"{selectedAccount?.account_name}"</strong>?
                </div>
                <div className="text-red-600 font-medium">
                  This will permanently delete:
                </div>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>The account and all its settings</li>
                  <li>All activities and activity logs</li>
                  <li>All metrics and measurements</li>
                  <li>All insights and intuitions</li>
                  <li>All other related data</li>
                </ul>
                <div className="text-red-600 font-semibold pt-2">
                  This action cannot be undone.
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteAccountMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <Button
              onClick={handleDeleteAccount}
              disabled={
                deleteAccountMutation.isPending || isOperationInProgress
              }
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600 text-white"
              variant="destructive"
            >
              {deleteAccountMutation.isPending
                ? "Deleting..."
                : "Delete Permanently"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TooltipProvider>
  );
};

export default AccountsManagement;
