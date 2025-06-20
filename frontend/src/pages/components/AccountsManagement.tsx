import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { User, Plus, X, Settings } from "lucide-react";
import {
  accounts,
  createNewAccount,
  INDUSTRY_OPTIONS,
  TIMEZONE_OPTIONS,
  type Organization,
  type Account,
} from "@/data/organizationData";

const REGION_OPTIONS = [
  { value: "North America", label: "North America" },
  { value: "Europe", label: "Europe" },
  { value: "Asia Pacific", label: "Asia Pacific" },
  { value: "Latin America", label: "Latin America" },
  { value: "Middle East & Africa", label: "Middle East & Africa" },
  { value: "Global", label: "Global" },
];

interface AccountsManagementProps {
  orgData: Organization;
  currentOrgId: string;
}

const AccountsManagement = ({
  orgData,
  currentOrgId,
}: AccountsManagementProps) => {
  // State for account management
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCreateAccountModalOpen, setIsCreateAccountModalOpen] =
    useState(false);

  const [editFormData, setEditFormData] = useState({
    account_name: "",
    industry: "",
    status: "",
    websites: [""],
    timezone: "",
    region: "",
  });

  const [createAccountFormData, setCreateAccountFormData] = useState({
    account_name: "",
    industry: "",
    status: "Active",
    websites: [""],
    timezone: "America/New_York",
    region: "North America",
  });

  // Get accounts for current organization
  const organizationAccounts = useMemo(() => {
    return accounts.filter(
      (account) => account.organization_id === currentOrgId,
    );
  }, [currentOrgId]);

  // Event handlers
  const handleEditAccount = (account: Account) => {
    setSelectedAccount(account);
    setEditFormData({
      account_name: account.account_name,
      industry: account.industry,
      status: account.status,
      websites:
        account.websites && account.websites.length > 0
          ? account.websites
          : [""],
      timezone: account.timezone || "America/New_York",
      region: (account as any).region || "North America",
    });
    setIsModalOpen(true);
  };

  const handleSaveAccount = () => {
    console.log("Saving account:", editFormData);
    setIsModalOpen(false);
    setSelectedAccount(null);
  };

  const handleCreateAccount = () => {
    if (
      !createAccountFormData.account_name ||
      !createAccountFormData.industry
    ) {
      alert("Please fill in required fields");
      return;
    }

    try {
      const newAccount = createNewAccount({
        ...createAccountFormData,
        organization_id: currentOrgId,
      });
      console.log("Account created successfully:", newAccount);

      setIsCreateAccountModalOpen(false);
      setCreateAccountFormData({
        account_name: "",
        industry: "",
        status: "Active",
        websites: [""],
        timezone: "America/New_York",
      });

      alert(`Account "${newAccount.account_name}" created successfully!`);
    } catch (error) {
      console.error("Error creating account:", error);
      alert("Failed to create account. Please try again.");
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
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Accounts
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsCreateAccountModalOpen(true)}
              className="h-8 w-8 p-0"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {organizationAccounts.length > 0 ? (
            organizationAccounts.map((account) => (
              <div
                key={account.account_id}
                className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <User className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900">
                      {account.account_name}
                    </h4>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className="text-xs">
                        {account.industry}
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
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleEditAccount(account)}
                  className="h-8 w-8 p-0"
                >
                  <Settings className="h-4 w-4 text-gray-500" />
                </Button>
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
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Account</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="account-name">Account Name</Label>
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
              <Select
                value={editFormData.industry}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    industry: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select industry" />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                  <SelectItem value="Retail">Retail</SelectItem>
                  <SelectItem value="Healthcare Services">
                    Healthcare Services
                  </SelectItem>
                  <SelectItem value="Financial Services">
                    Financial Services
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-status">Status</Label>
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
                  <SelectItem value="Suspended">Suspended</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-timezone">Timezone</Label>
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
              <Label htmlFor="account-region">Customer Region</Label>
              <Select
                value={editFormData.region}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    region: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select customer region" />
                </SelectTrigger>
                <SelectContent>
                  {REGION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Websites</Label>
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
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => setIsModalOpen(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button onClick={handleSaveAccount} className="flex-1">
                Save Changes
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Account Modal */}
      <Dialog
        open={isCreateAccountModalOpen}
        onOpenChange={setIsCreateAccountModalOpen}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create New Account</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="create-account-name">Account Name</Label>
              <Input
                id="create-account-name"
                value={createAccountFormData.account_name}
                onChange={(e) =>
                  setCreateAccountFormData({
                    ...createAccountFormData,
                    account_name: e.target.value,
                  })
                }
                placeholder="Enter account name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-account-industry">Industry</Label>
              <Select
                value={createAccountFormData.industry}
                onValueChange={(value) =>
                  setCreateAccountFormData({
                    ...createAccountFormData,
                    industry: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select industry" />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                  <SelectItem value="Retail">Retail</SelectItem>
                  <SelectItem value="Healthcare Services">
                    Healthcare Services
                  </SelectItem>
                  <SelectItem value="Financial Services">
                    Financial Services
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-account-status">Status</Label>
              <Select
                value={createAccountFormData.status}
                onValueChange={(value) =>
                  setCreateAccountFormData({
                    ...createAccountFormData,
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
                  <SelectItem value="Suspended">Suspended</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-account-timezone">Timezone</Label>
              <Select
                value={createAccountFormData.timezone}
                onValueChange={(value) =>
                  setCreateAccountFormData({
                    ...createAccountFormData,
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
              <div className="flex items-center justify-between">
                <Label>Websites</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addCreateWebsiteField}
                  className="h-8 w-8 p-0"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {createAccountFormData.websites.map((website, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={website}
                      onChange={(e) =>
                        updateCreateWebsiteField(index, e.target.value)
                      }
                      placeholder="Enter website URL"
                      className="flex-1"
                    />
                    {createAccountFormData.websites.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeCreateWebsiteField(index)}
                        className="h-10 w-10 p-0 text-red-500 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => setIsCreateAccountModalOpen(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button onClick={handleCreateAccount} className="flex-1">
                Create Account
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AccountsManagement;
