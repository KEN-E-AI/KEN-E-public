import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  getOrganizations,
  getOrganizationById,
  getAccountsByOrganizationId,
  createAccount,
  getChildOrganizations,
} from "@/data/organizationApi";
import {
  validateAccountCreationRequirements,
  getTargetOrganizationId,
  resolveOrganizationAndAccount,
  formatWorkspaceMetadata,
} from "@/lib/organizationUtils";
import {
  ACCOUNT_CREATION_REDIRECT_DELAY,
  WORKSPACE_SELECTION_DELAY,
  DEFAULT_TIMEZONE,
  DEFAULT_DATA_REGION,
  DEFAULT_ACCOUNT_STATUS,
  DEFAULT_REGION,
  ACCOUNT_CREATION_SUCCESS_TITLE,
  ACCOUNT_CREATION_SUCCESS_DESCRIPTION,
  AGENCY_ORGANIZATION_MESSAGE,
} from "@/constants/organizationSelection";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building, Plus, Check, ArrowRight, Settings } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useChildOrganizations } from "@/hooks/useChildOrganizations";
import { useAvailableAccounts } from "@/hooks/useAvailableAccounts";

interface OrganizationSelectionProps {
  onComplete: () => void;
}

/**
 * Creates an account in the correct organization (regular or child)
 */
async function createAccountInCorrectOrganization(
  accountName: string,
  accountType: string,
  selectedOrganization: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
) {
  const targetOrgId = getTargetOrganizationId(
    selectedOrganization,
    selectedChildOrg,
    localOrgMetadata,
  );

  return await createAccount({
    account_name: accountName,
    organization_id: targetOrgId,
    industry: accountType || "Unknown",
    status: DEFAULT_ACCOUNT_STATUS,
    websites: [],
    timezone: DEFAULT_TIMEZONE,
    data_region: DEFAULT_DATA_REGION,
    region: DEFAULT_REGION,
  });
}

/**
 * Handles successful account creation UI updates
 */
function handleAccountCreationSuccess(
  newAccount: any,
  setAccountMetadata: (fn: (prev: any) => any) => void,
  setShowCreateAccount: (show: boolean) => void,
  setNewAccountData: (data: any) => void,
  setSelectedAccount: (accountId: string) => void,
  toast: any,
) {
  const newAccountId = newAccount.account_id;

  // Update local state
  setAccountMetadata((prev) => ({
    ...prev,
    [newAccountId]: newAccount,
  }));

  setShowCreateAccount(false);
  setNewAccountData({ name: "", type: "", description: "" });

  // Set the newly created account as selected
  setSelectedAccount(newAccountId);

  // Toast user of successful creation
  toast({
    title: ACCOUNT_CREATION_SUCCESS_TITLE,
    description: ACCOUNT_CREATION_SUCCESS_DESCRIPTION(newAccount.account_name),
  });

  return newAccountId;
}

/**
 * Handles workspace selection and navigation after account creation
 */
function navigateToAccountSettings(
  newAccountId: string,
  selectedOrganization: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
  childOrganizations: Record<string, any>[],
  newAccount: any,
  setSelectedOrgAccount: any,
  setCurrentOrganization: any,
  completeWorkspaceSelection: any,
  navigate: any,
) {
  const resolution = resolveOrganizationAndAccount(
    selectedOrganization,
    newAccountId,
    selectedChildOrg,
    localOrgMetadata,
    childOrganizations,
  );

  const account = resolution.account || newAccount;
  const metadata = formatWorkspaceMetadata(
    resolution.organization?.organization_name || resolution.organizationId,
    account?.account_name || newAccount.account_name,
    account?.industry || newAccount.industry || "Unknown",
    account?.status || newAccount.status || DEFAULT_ACCOUNT_STATUS,
    account?.timezone || newAccount.timezone,
    resolution.organization?.plan,
  );

  setSelectedOrgAccount({
    orgId: resolution.organizationId,
    accountId: newAccountId,
    metadata,
  });
  setCurrentOrganization(resolution.organizationId);
  completeWorkspaceSelection();

  // Navigate to account settings instead of home
  navigate("/account-settings");
}

/**
 * Handles account creation errors
 */
function handleAccountCreationError(err: any, toast: any) {
  console.error("Failed to create account", err);
  const errorMessage =
    err.response?.data?.detail ||
    err.message ||
    "Error creating account. Please try again.";
  toast({
    title: "Error",
    description: errorMessage,
    variant: "destructive",
  });
}

const OrganizationSelection = ({ onComplete }: OrganizationSelectionProps) => {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const navigate = useNavigate();
  const { toast } = useToast();
  const {
    user,
    setSelectedOrgAccount,
    completeWorkspaceSelection,
    setCurrentOrganization,
    setOrgMetadata,
    setAccountMetadata,
  } = useAuth();
  const [selectedOrganization, setSelectedOrganization] = useState<string>("");
  const [selectedAccount, setSelectedAccount] = useState<string>("");
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  // const [showCreateAccount, setShowCreateAccount] = useState(false); // Removed - using redirect instead
  const [isLoading, setIsLoading] = useState(false);
  const [orgsFromFirestore, setOrgsFromFirestore] = useState<
    Record<string, string>
  >({});
  // Note: accountsFromFirestore removed - users now inherit account access from organization permissions
  const [loadingUserData, setLoadingUserData] = useState(true);
  const [localOrgMetadata, setLocalOrgMetadata] = useState<Record<string, any>>(
    {},
  );
  const [selectedChildOrg, setSelectedChildOrg] = useState<string>("");

  // Use custom hooks for child organizations and available accounts
  const {
    childOrganizations,
    loading: childOrganizationsLoading,
    error: childOrganizationsError,
    fetchChildOrganizations,
    clearChildOrganizations,
  } = useChildOrganizations();

  // Define function for getting accounts by organization ID from local state
  const getAccountsByOrganizationIdFromLocal = (orgId: string) => {
    const orgAccounts: any[] = localOrgMetadata[orgId]?.accounts || [];

    // Check if user has access to the organization
    const hasOrgAccess = orgId in orgsFromFirestore;

    if (!hasOrgAccess) {
      return [];
    }

    // If user has organization access, they can see all accounts in that organization
    return orgAccounts
      .map((account) => ({
        account_id: account.account_id,
        account_name:
          account.account_name || account.account_id.replace(/-/g, " "),
        industry: account.industry || "Unknown",
        status: account.status || "Active",
        permission: orgsFromFirestore[orgId], // Use organization permission level
      }))
      .sort((a, b) => a.account_name.localeCompare(b.account_name));
  };

  const {
    availableAccounts,
    hasAccounts,
    isAgencyOrganization,
    needsChildOrgSelection,
  } = useAvailableAccounts({
    selectedOrganization,
    selectedChildOrg,
    localOrgMetadata,
    childOrganizations,
    orgsFromFirestore,
    getAccountsByOrganizationIdFromLocal,
  });

  const [newOrgData, setNewOrgData] = useState({
    name: "",
    industry: "",
  });

  const [newAccountData, setNewAccountData] = useState({
    name: "",
    type: "",
    description: "",
  });
  const FIRESTORE_USER_ID = user?.id;

  useEffect(() => {
    if (!FIRESTORE_USER_ID) return;

    const fetchUserData = async () => {
      try {
        const res = await axios.get(
          `${API_BASE_URL}/api/v1/firestore/documents/users/${FIRESTORE_USER_ID}`,
        );
        const { data } = res.data;
        setOrgsFromFirestore(data.permissions.organizations || {});
        // Note: No longer fetching account permissions - users inherit access from organization permissions
      } catch (error) {
        console.error("Failed to fetch user org/account data", error);
      } finally {
        setLoadingUserData(false);
      }
    };

    fetchUserData();
  }, [FIRESTORE_USER_ID]);

  useEffect(() => {
    if (!loadingUserData && Object.keys(orgsFromFirestore).length === 0) {
      navigate("/create-organization");
    }
  }, [loadingUserData, orgsFromFirestore]);

  useEffect(() => {
    const fetchOrgMetadata = async () => {
      const entries: [string, any][] = await Promise.all(
        Object.keys(orgsFromFirestore).map(async (orgId) => {
          try {
            // Fetch from Neo4j as the source of truth
            const org = await getOrganizationById(orgId);

            // Fetch accounts for this organization
            const accounts = await getAccountsByOrganizationId(orgId);

            if (org) {
              return [orgId, { ...org, accounts }];
            } else {
              // Organization not found - this is expected for some users
              return [
                orgId,
                { organization_id: orgId, organization_name: orgId, accounts },
              ];
            }
          } catch (err: any) {
            // Handle deleted organizations gracefully
            if (
              err.response?.status === 404 ||
              err.message ===
                `Resource not found: /api/v1/organizations/${orgId}`
            ) {
              // Organization was deleted but user still has permissions
              // Return null to filter it out later
              return [orgId, null];
            }

            // Log other errors
            console.error(`Failed to load org metadata for ${orgId}`, err);
            return [
              orgId,
              {
                organization_id: orgId,
                organization_name: orgId,
                accounts: [],
                error: true,
              },
            ];
          }
        }),
      );

      // Filter out null entries (deleted organizations)
      const filteredEntries = entries.filter(([_, value]) => value !== null);
      const result = Object.fromEntries(filteredEntries);

      // Also remove deleted organizations from orgsFromFirestore
      const deletedOrgIds = entries
        .filter(([_, value]) => value === null)
        .map(([orgId, _]) => orgId);

      if (deletedOrgIds.length > 0) {
        console.warn(
          `Found ${deletedOrgIds.length} deleted organizations in user permissions:`,
          deletedOrgIds,
        );

        // Update orgsFromFirestore to remove deleted organizations
        setOrgsFromFirestore((prev) => {
          const updated = { ...prev };
          deletedOrgIds.forEach((orgId) => delete updated[orgId]);
          return updated;
        });
      }

      setLocalOrgMetadata(result);
      setOrgMetadata(result); // from context

      const flattenedAccounts: Record<string, any> = {};
      Object.values(result).forEach((org: any) => {
        (org.accounts || []).forEach((acc: any) => {
          flattenedAccounts[acc.account_id] = acc;
        });
      });
      setAccountMetadata(flattenedAccounts); // from context
    };

    if (Object.keys(orgsFromFirestore).length > 0) {
      fetchOrgMetadata();
    }
  }, [orgsFromFirestore]);

  const organizationList = Object.entries(orgsFromFirestore).map(
    ([orgId, permission]) => {
      const metadata = localOrgMetadata[orgId] || {};
      return {
        organization_id: orgId,
        organization_name:
          metadata.organization_name || orgId.replace(/-/g, " "),
        permission,
        error: metadata.error || false,
        ...metadata,
      };
    },
  );

  const handleCreateOrganization = () => {
    setIsLoading(true);
    // Simulate organization creation
    setTimeout(() => {
      setIsLoading(false);
      setShowCreateOrg(false);
      setNewOrgData({ name: "", industry: "" });
    }, 1500);
  };

  const handleNavigateToNewOrganization = () => {
    navigate("/create-organization");
  };

  // Removed - now redirecting to complete form instead
  /* const handleCreateAccount = async () => {
    // Validate account creation requirements
    const validation = validateAccountCreationRequirements(
      selectedOrganization,
      selectedChildOrg,
      localOrgMetadata,
      newAccountData.name,
      newAccountData.type,
    );

    if (!validation.isValid) {
      toast({
        title: "Validation Error",
        description: validation.errorMessage,
        variant: "destructive",
      });
      return;
    }

    try {
      setIsLoading(true);

      // Create account in the correct organization
      const newAccount = await createAccountInCorrectOrganization(
        newAccountData.name,
        newAccountData.type,
        selectedOrganization,
        selectedChildOrg,
        localOrgMetadata,
      );

      // Handle successful account creation
      const newAccountId = handleAccountCreationSuccess(
        newAccount,
        setAccountMetadata,
        setShowCreateAccount,
        setNewAccountData,
        setSelectedAccount,
        toast,
      );

      // Auto-navigate to account settings after successful account creation
      setTimeout(() => {
        navigateToAccountSettings(
          newAccountId,
          selectedOrganization,
          selectedChildOrg,
          localOrgMetadata,
          childOrganizations,
          newAccount,
          setSelectedOrgAccount,
          setCurrentOrganization,
          completeWorkspaceSelection,
          navigate,
        );
      }, ACCOUNT_CREATION_REDIRECT_DELAY);
    } catch (err: any) {
      handleAccountCreationError(err, toast);
    } finally {
      setIsLoading(false);
    }
  }; */

  const handleContinue = () => {
    if (selectedOrganization && selectedAccount) {
      setIsLoading(true);
      // Simulate selection processing
      setTimeout(() => {
        const resolution = resolveOrganizationAndAccount(
          selectedOrganization,
          selectedAccount,
          selectedChildOrg,
          localOrgMetadata,
          childOrganizations,
        );

        const metadata = formatWorkspaceMetadata(
          resolution.organization?.organization_name || selectedOrganization,
          resolution.account?.account_name || selectedAccount,
          resolution.account?.industry || "Unknown",
          resolution.account?.status || "Active",
          resolution.account?.timezone,
          resolution.organization?.plan,
        );

        setSelectedOrgAccount({
          orgId: resolution.organizationId,
          accountId: selectedAccount,
          metadata,
        });
        setCurrentOrganization(resolution.organizationId);
        completeWorkspaceSelection();

        onComplete();
      }, WORKSPACE_SELECTION_DELAY);
    }
  };

  const selectedOrgData = organizationList.find(
    (org) => org.organization_id === selectedOrganization,
  );

  const handleOrganizationSelect = async (orgId: string) => {
    if (orgId !== selectedOrganization) {
      setSelectedAccount(""); // Reset account selection
      setSelectedChildOrg(""); // Reset child organization selection
      clearChildOrganizations(); // Clear child organizations
    }
    setSelectedOrganization(orgId);

    // If this is an agency organization, fetch child organizations
    const selectedOrg = localOrgMetadata[orgId];
    if (selectedOrg && selectedOrg.agency) {
      await fetchChildOrganizations(orgId);
    }
  };

  if (loadingUserData || Object.keys(localOrgMetadata).length === 0) {
    return (
      <div className="text-center py-10 text-gray-500">
        Loading organizations...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8 pt-8">
          <div className="flex items-center justify-center mb-4">
            <img
              src="/KEN-E Logo E Small.png"
              alt="KEN-E Logo"
              className="h-16 w-auto"
            />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Select An Account
          </h1>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Organization Selection */}
          <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
            <CardHeader>
              <CardTitle>Select Organization</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {organizationList.map((org) => (
                <div
                  key={org.organization_id}
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                    selectedOrganization === org.organization_id
                      ? "border-brand-medium-blue bg-brand-light-blue/20"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                  onClick={() => handleOrganizationSelect(org.organization_id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {org.organization_name}
                        </h3>
                        {org.error && (
                          <Badge variant="destructive" className="text-xs">
                            Error Loading
                          </Badge>
                        )}
                        {selectedOrganization === org.organization_id && (
                          <Check className="h-4 w-4 text-brand-medium-blue" />
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        // Set the organization as current
                        setCurrentOrganization(org.organization_id);
                        
                        // Set the selectedOrgAccount to show in the dropdown
                        const firstAccount = org.accounts?.[0];
                        setSelectedOrgAccount({
                          orgId: org.organization_id,
                          accountId: firstAccount?.account_id || "",
                          metadata: {
                            organization_name: org.organization_name,
                            account_name: firstAccount?.account_name || "",
                            industry: firstAccount?.industry || "",
                            status: firstAccount?.status || "Active",
                            timezone: firstAccount?.timezone || "",
                            plan: org.plan,
                          },
                        });
                        
                        // Complete workspace selection to allow navigation
                        completeWorkspaceSelection();
                        // Navigate to organization settings
                        navigate("/settings/organization");
                      }}
                    >
                      <Settings className="h-4 w-4" />
                      <span className="sr-only">Organization settings</span>
                    </Button>
                  </div>
                </div>
              ))}

              <Button
                variant="outline"
                className="w-full"
                onClick={handleNavigateToNewOrganization}
              >
                <Plus className="h-4 w-4 mr-2" />
                Create New Organization
              </Button>
            </CardContent>
          </Card>

          {/* Account Selection */}
          <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
            <CardHeader>
              <CardTitle>Select Account</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedOrgData ? (
                <>
                  <div className="p-3 bg-brand-light-blue/20 border border-brand-light-blue/40 rounded-lg mb-4">
                    <p className="text-sm text-brand-dark-blue">
                      <strong>{selectedOrgData.organization_name}</strong>{" "}
                      selected
                    </p>
                  </div>

                  {/* Agency Organization Handling */}
                  {selectedOrgData.agency ? (
                    <>
                      <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg mb-4">
                        <p className="text-sm text-orange-800">
                          {AGENCY_ORGANIZATION_MESSAGE}
                        </p>
                      </div>

                      {/* Child Organization Selection */}
                      <div className="space-y-3">
                        <Label className="text-sm font-medium">
                          Client Organizations
                        </Label>
                        {childOrganizations.map((childOrg) => (
                          <div
                            key={childOrg.organization_id}
                            className={`p-3 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                              selectedChildOrg === childOrg.organization_id
                                ? "border-brand-medium-blue bg-brand-light-blue/20"
                                : "border-gray-200 hover:border-gray-300"
                            }`}
                            onClick={() =>
                              setSelectedChildOrg(childOrg.organization_id)
                            }
                          >
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium text-gray-900">
                                {childOrg.organization_name}
                              </h4>
                              {selectedChildOrg ===
                                childOrg.organization_id && (
                                <Check className="h-4 w-4 text-brand-medium-blue" />
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Show accounts for selected child organization */}
                      {selectedChildOrg && (
                        <div className="mt-4 space-y-3">
                          <Label className="text-sm font-medium">
                            Accounts
                          </Label>
                          {availableAccounts.map((account) => (
                            <div
                              key={account.account_id}
                              className={`p-4 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                                selectedAccount === account.account_id
                                  ? "border-brand-medium-blue bg-brand-light-blue/20"
                                  : "border-gray-200 hover:border-gray-300"
                              }`}
                              onClick={() =>
                                setSelectedAccount(account.account_id)
                              }
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-2">
                                    <h3 className="font-semibold text-gray-900">
                                      {account.account_name}
                                    </h3>
                                    {selectedAccount === account.account_id && (
                                      <Check className="h-4 w-4 text-brand-medium-blue" />
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2 mb-2">
                                    <Badge
                                      variant={
                                        account.industry === "Retail"
                                          ? "default"
                                          : account.industry ===
                                              "Healthcare Services"
                                            ? "secondary"
                                            : account.industry ===
                                                "Financial Services"
                                              ? "outline"
                                              : "outline"
                                      }
                                      className="text-xs"
                                    >
                                      {account.industry}
                                    </Badge>
                                    <Badge
                                      variant="outline"
                                      className="text-xs text-brand-light-green border-brand-light-green/40"
                                    >
                                      {account.status}
                                    </Badge>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}

                          <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => {
                              // Set the organization as current
                              setCurrentOrganization(selectedOrganization);

                              // Complete workspace selection to allow navigation
                              completeWorkspaceSelection();

                              // Navigate to organization settings with create account flag
                              navigate(
                                "/settings/organization?openCreateAccount=true",
                              );
                            }}
                          >
                            <Plus className="h-4 w-4 mr-2" />
                            Create New Account
                          </Button>
                        </div>
                      )}
                    </>
                  ) : (
                    /* Regular Organization Handling */
                    <>
                      {availableAccounts.map((account) => (
                        <div
                          key={account.account_id}
                          className={`p-4 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                            selectedAccount === account.account_id
                              ? "border-brand-medium-blue bg-brand-light-blue/20"
                              : "border-gray-200 hover:border-gray-300"
                          }`}
                          onClick={() => setSelectedAccount(account.account_id)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <h3 className="font-semibold text-gray-900">
                                  {account.account_name}
                                </h3>
                                {selectedAccount === account.account_id && (
                                  <Check className="h-4 w-4 text-brand-medium-blue" />
                                )}
                              </div>
                              <div className="flex items-center gap-2 mb-2">
                                <Badge
                                  variant={
                                    account.industry === "Retail"
                                      ? "default"
                                      : account.industry ===
                                          "Healthcare Services"
                                        ? "secondary"
                                        : account.industry ===
                                            "Financial Services"
                                          ? "outline"
                                          : "outline"
                                  }
                                  className="text-xs"
                                >
                                  {account.industry}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="text-xs text-brand-light-green border-brand-light-green/40"
                                >
                                  {account.status}
                                </Badge>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}

                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={() => {
                          const orgToSet = selectedOrgData.agency
                            ? selectedChildOrg || selectedOrganization
                            : selectedOrganization;

                          if (!orgToSet) {
                            toast({
                              title: "No organization selected",
                              description:
                                "Please select an organization first",
                              variant: "destructive",
                            });
                            return;
                          }

                          // Set the organization as current
                          setCurrentOrganization(orgToSet);

                          // Complete workspace selection to allow navigation
                          completeWorkspaceSelection();

                          // Navigate to organization settings with create account flag
                          navigate(
                            "/settings/organization?openCreateAccount=true",
                          );
                        }}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Create New Account
                      </Button>
                    </>
                  )}
                </>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Settings className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>Please select an organization first</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Continue Button */}
        <div className="flex justify-center mt-8">
          <Button
            onClick={handleContinue}
            disabled={
              !selectedOrganization ||
              !selectedAccount ||
              isLoading ||
              (selectedOrgData?.agency && !selectedChildOrg)
            }
            className="px-8 py-3"
            size="lg"
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Setting up workspace...
              </div>
            ) : (
              <div className="flex items-center gap-2">
                Continue
                <ArrowRight className="h-4 w-4" />
              </div>
            )}
          </Button>
        </div>

        {/* Create Organization Dialog */}
        <Dialog open={showCreateOrg} onOpenChange={setShowCreateOrg}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create New Organization</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="org-name">Organization Name</Label>
                <Input
                  id="org-name"
                  placeholder="Enter organization name"
                  value={newOrgData.name}
                  onChange={(e) =>
                    setNewOrgData({ ...newOrgData, name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="org-industry">Industry</Label>
                <Select
                  value={newOrgData.industry}
                  onValueChange={(value) =>
                    setNewOrgData({ ...newOrgData, industry: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select industry" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="technology">Technology</SelectItem>
                    <SelectItem value="marketing">Marketing</SelectItem>
                    <SelectItem value="finance">Finance</SelectItem>
                    <SelectItem value="healthcare">Healthcare</SelectItem>
                    <SelectItem value="retail">Retail</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowCreateOrg(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateOrganization}
                  disabled={
                    !newOrgData.name || !newOrgData.industry || isLoading
                  }
                  className="flex-1"
                >
                  {isLoading ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    "Create"
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Create Account Dialog - Removed in favor of redirecting to the complete form */}
      </div>
    </div>
  );
};

export default OrganizationSelection;
