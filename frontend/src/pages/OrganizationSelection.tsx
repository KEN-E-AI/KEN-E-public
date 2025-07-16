import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  getOrganizations,
  getOrganizationById,
  getAccountsByOrganizationId,
  createAccount,
} from "@/data/organizationApi";
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

interface OrganizationSelectionProps {
  onComplete: () => void;
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
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [orgsFromFirestore, setOrgsFromFirestore] = useState<
    Record<string, string>
  >({});
  // Note: accountsFromFirestore removed - users now inherit account access from organization permissions
  const [loadingUserData, setLoadingUserData] = useState(true);
  const [localOrgMetadata, setLocalOrgMetadata] = useState<Record<string, any>>(
    {},
  );

  const [newOrgData, setNewOrgData] = useState({
    name: "",
    industry: "",
    size: "",
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
              console.warn(`Organization ${orgId} not found in Neo4j`);
              return [
                orgId,
                { organization_id: orgId, organization_name: orgId, accounts },
              ];
            }
          } catch (err) {
            console.error(
              `Failed to load org metadata for ${orgId} from Neo4j`,
              err,
            );
            return [
              orgId,
              {
                organization_id: orgId,
                organization_name: orgId,
                accounts: [],
              },
            ];
          }
        }),
      );

      const result = Object.fromEntries(entries);
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
        ...metadata,
      };
    },
  );

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

  const handleCreateOrganization = () => {
    setIsLoading(true);
    // Simulate organization creation
    setTimeout(() => {
      setIsLoading(false);
      setShowCreateOrg(false);
      setNewOrgData({ name: "", industry: "", size: "" });
    }, 1500);
  };

  const handleNavigateToNewOrganization = () => {
    navigate("/create-organization");
  };

  const handleCreateAccount = async () => {
    if (!selectedOrganization) {
      alert("Please select an organization first.");
      return;
    }

    if (!newAccountData.name || !newAccountData.type) {
      alert("Please fill in all required fields");
      return;
    }

    try {
      setIsLoading(true);

      // Create account in Neo4j (source of truth)
      const newAccount = await createAccount({
        account_name: newAccountData.name,
        organization_id: selectedOrganization,
        industry: newAccountData.type || "Unknown",
        status: "Active",
        websites: [],
        timezone: "America/New_York",
        data_region: "United States",
        region: [],
      });

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
        title: "Account created successfully!",
        description: `"${newAccount.account_name}" has been created. Redirecting to account settings...`,
      });

      // Auto-navigate to account settings after successful account creation
      setTimeout(() => {
        // Set the workspace selection data before navigating
        const org = localOrgMetadata[selectedOrganization];
        const account =
          org?.accounts?.find((a: any) => a.account_id === newAccountId) ||
          newAccount;

        setSelectedOrgAccount({
          orgId: selectedOrganization,
          accountId: newAccountId,
          metadata: {
            organization_name: org?.organization_name || selectedOrganization,
            account_name: account?.account_name || newAccount.account_name,
            industry: account?.industry || newAccount.industry || "Unknown",
            status: account?.status || newAccount.status || "Active",
            timezone: account?.timezone || newAccount.timezone,
            plan: org?.plan,
          },
        });
        setCurrentOrganization(selectedOrganization);
        completeWorkspaceSelection();

        // Navigate to account settings instead of home
        navigate("/account-settings");
      }, 1500); // 1.5 second delay to show the toast
    } catch (err: any) {
      console.error("Failed to create account", err);
      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        "Error creating account. Please try again.";
      alert(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleContinue = () => {
    if (selectedOrganization && selectedAccount) {
      setIsLoading(true);
      // Simulate selection processing
      setTimeout(() => {
        // Create the combined org-account ID for the dropdown
        const org = localOrgMetadata[selectedOrganization];
        const account = org?.accounts?.find(
          (a: any) => a.account_id === selectedAccount,
        );

        setSelectedOrgAccount({
          orgId: selectedOrganization,
          accountId: selectedAccount,
          metadata: {
            organization_name: org?.organization_name || selectedOrganization,
            account_name: account?.account_name || selectedAccount,
            industry: account?.industry || "Unknown",
            status: account?.status || "Active",
            timezone: account?.timezone,
            plan: org?.plan,
          },
        });
        setCurrentOrganization(selectedOrganization);
        completeWorkspaceSelection();

        onComplete();
      }, 1000);
    }
  };

  const selectedOrgData = organizationList.find(
    (org) => org.organization_id === selectedOrganization,
  );

  // Filter accounts based on selected organization
  const availableAccounts = selectedOrganization
    ? getAccountsByOrganizationIdFromLocal(selectedOrganization)
    : [];
  const handleOrganizationSelect = (orgId: string) => {
    if (orgId !== selectedOrganization) {
      setSelectedAccount(""); // Reset account selection
    }
    setSelectedOrganization(orgId);
  };

  if (loadingUserData || Object.keys(localOrgMetadata).length === 0) {
    return (
      <div className="text-center py-10 text-gray-500">
        Loading organizations...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8 pt-8">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
              <Building className="h-6 w-6 text-white" />
            </div>
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
                      ? "border-blue-500 bg-blue-50"
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
                        {selectedOrganization === org.organization_id && (
                          <Check className="h-4 w-4 text-blue-600" />
                        )}
                      </div>
                    </div>
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
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4">
                    <p className="text-sm text-blue-800">
                      <strong>{selectedOrgData.organization_name}</strong>{" "}
                      selected
                    </p>
                  </div>

                  {availableAccounts.map((account) => (
                    <div
                      key={account.account_id}
                      className={`p-4 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                        selectedAccount === account.account_id
                          ? "border-blue-500 bg-blue-50"
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
                              <Check className="h-4 w-4 text-blue-600" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 mb-2">
                            <Badge
                              variant={
                                account.industry === "Retail"
                                  ? "default"
                                  : account.industry === "Healthcare Services"
                                    ? "secondary"
                                    : account.industry === "Financial Services"
                                      ? "outline"
                                      : "outline"
                              }
                              className="text-xs"
                            >
                              {account.industry}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="text-xs text-green-600 border-green-200"
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
                    onClick={() => setShowCreateAccount(true)}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Create New Account
                  </Button>
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
            disabled={!selectedOrganization || !selectedAccount || isLoading}
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
              <div className="space-y-2">
                <Label htmlFor="org-size">Company Size</Label>
                <Select
                  value={newOrgData.size}
                  onValueChange={(value) =>
                    setNewOrgData({ ...newOrgData, size: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select company size" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1-10">1-10 employees</SelectItem>
                    <SelectItem value="11-50">11-50 employees</SelectItem>
                    <SelectItem value="51-200">51-200 employees</SelectItem>
                    <SelectItem value="201-1000">201-1000 employees</SelectItem>
                    <SelectItem value="1000+">1000+ employees</SelectItem>
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
                    !newOrgData.name ||
                    !newOrgData.industry ||
                    !newOrgData.size ||
                    isLoading
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

        {/* Create Account Dialog */}
        <Dialog open={showCreateAccount} onOpenChange={setShowCreateAccount}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create New Account</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="account-name">Account Name</Label>
                <Input
                  id="account-name"
                  placeholder="Enter account name"
                  value={newAccountData.name}
                  onChange={(e) =>
                    setNewAccountData({
                      ...newAccountData,
                      name: e.target.value,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-type">Account Type</Label>
                <Select
                  value={newAccountData.type}
                  onValueChange={(value) =>
                    setNewAccountData({ ...newAccountData, type: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select account type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="production">Production</SelectItem>
                    <SelectItem value="development">Development</SelectItem>
                    <SelectItem value="staging">Staging</SelectItem>
                    <SelectItem value="analytics">Analytics</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-description">Description</Label>
                <Input
                  id="account-description"
                  placeholder="Brief description (optional)"
                  value={newAccountData.description}
                  onChange={(e) =>
                    setNewAccountData({
                      ...newAccountData,
                      description: e.target.value,
                    })
                  }
                />
              </div>
              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowCreateAccount(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateAccount}
                  disabled={
                    !newAccountData.name || !newAccountData.type || isLoading
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
      </div>
    </div>
  );
};

export default OrganizationSelection;
