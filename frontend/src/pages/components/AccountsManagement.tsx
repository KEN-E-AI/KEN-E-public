import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { User, Plus, X, Settings, Check, ChevronDown } from "lucide-react";
import {
  INDUSTRY_OPTIONS,
  TIMEZONE_OPTIONS,
  type Organization,
  type Account,
} from "@/data/organizationData";

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
}

const AccountsManagement = ({
  orgData,
  currentOrgId,
}: AccountsManagementProps) => {
  const { accountMetadata, setAccountMetadata, user } = useAuth();
  // State for account management
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCreateAccountModalOpen, setIsCreateAccountModalOpen] =
    useState(false);
  const [isEditRegionPopoverOpen, setIsEditRegionPopoverOpen] = useState(false);
  const [isCreateRegionPopoverOpen, setIsCreateRegionPopoverOpen] =
    useState(false);

  // Refs for click-outside handling
  const editRegionDropdownRef = useRef<HTMLDivElement>(null);
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
    industry: "",
    status: "",
    websites: [""],
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
    data_region: "United States",
    region: [] as string[],
  });

  const organizationAccounts = useMemo(() => {
    if (!orgData?.accounts || !user?.permissions?.accounts) return [];

    return orgData.accounts
      .filter((a: any) => user.permissions.accounts?.[a.account_id])
      .map((a: any) => accountMetadata[a.account_id])
      .filter(Boolean); // remove undefined
  }, [orgData, accountMetadata, user]);

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
    setSelectedAccount(account);
    const existingRegion = (account as any).region;
    let regionArray: string[] = [];

    if (Array.isArray(existingRegion)) {
      regionArray = existingRegion;
    } else if (typeof existingRegion === "string" && existingRegion) {
      regionArray = [existingRegion];
    }

    setEditFormData({
      account_name: account.account_name,
      industry: account.industry,
      status: account.status,
      websites:
        account.websites && account.websites.length > 0
          ? account.websites
          : [""],
      timezone: account.timezone || "America/New_York",
      data_region: (account as any).data_region || "United States",
      region: regionArray,
    });
    setIsModalOpen(true);
  };

  const handleSaveAccount = async () => {
    if (!selectedAccount) return;

    try {
      const updatedAccount = {
        ...selectedAccount,
        ...editFormData,
      };

      await axios.put(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/organizations/${currentOrgId}?account_id=${currentOrgId}`,
        {
          update: {
            field: "accounts",
            operator: "replaceOne",
            matchField: "account_id",
            matchValue: selectedAccount.account_id,
            value: updatedAccount,
          },
        }
      );

      // Optionally update local accountMetadata context
      setAccountMetadata((prev) => ({
        ...prev,
        [selectedAccount.account_id]: updatedAccount,
      }));

      setIsModalOpen(false);
      setSelectedAccount(null);
      alert("Account updated successfully.");
    } catch (error) {
      console.error("Error saving account:", error);
      alert("Failed to update account. Please try again.");
    }
  };


  const handleCreateAccount = async () => {
    if (
      !createAccountFormData.account_name ||
      !createAccountFormData.industry
    ) {
      alert("Please fill in required fields");
      return;
    }

    try {
      const newAccountId = createAccountFormData.account_name
        .toLowerCase()
        .replace(/\s+/g, "-");

      const newAccount = {
        ...createAccountFormData,
        account_id: newAccountId,
      };

      // 🔁 PATCH the organization to add a new account
      await axios.put(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/organizations/${currentOrgId}?account_id=${currentOrgId}`,
        {
          update: {
            field: "accounts",
            operator: "arrayUnion",
            value: newAccount,
          },
        }
      );

      // await axios.put(
      //   `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/users/${user?.id}?account_id=${user?.id}`,
      //   {
      //     update: {
      //       // This is a nested field path for dot-notation update
      //       field: `permissions.accounts.${newAccountId}`,
      //       operator: "set",
      //       value: "admin",
      //     },
      //   }
      // );

      // 🧠 Optionally update local context
      const updatedAccounts = [...(orgData?.accounts || []), newAccount];
      setAccountMetadata({
        ...accountMetadata,
        [newAccountId]: newAccount,
      });

      // You may also want to update `orgMetadata` here:
      // setOrgMetadata((prev) => ({
      //   ...prev,
      //   [currentOrgId]: {
      //     ...prev[currentOrgId],
      //     accounts: updatedAccounts,
      //   }
      // }));

      setIsCreateAccountModalOpen(false);
      setCreateAccountFormData({
        account_name: "",
        industry: "",
        status: "Active",
        websites: [""],
        timezone: "America/New_York",
        data_region: "United States",
        region: [],
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
              <Label htmlFor="account-data-region">Data Region</Label>
              <Select
                value={editFormData.data_region}
                onValueChange={(value) =>
                  setEditFormData({
                    ...editFormData,
                    data_region: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select data region" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="United States">United States</SelectItem>
                  <SelectItem value="Europe">Europe</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Customer Region</Label>
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
              <Label htmlFor="create-account-data-region">Data Region</Label>
              <Select
                value={createAccountFormData.data_region}
                onValueChange={(value) =>
                  setCreateAccountFormData({
                    ...createAccountFormData,
                    data_region: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select data region" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="United States">United States</SelectItem>
                  <SelectItem value="Europe">Europe</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Customer Region</Label>
                <div className="relative" ref={createRegionDropdownRef}>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() =>
                      setIsCreateRegionPopoverOpen(!isCreateRegionPopoverOpen)
                    }
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                  {isCreateRegionPopoverOpen && (
                    <div className="absolute top-full right-0 mt-1 w-80 bg-white border border-gray-200 rounded-md shadow-lg z-50 max-h-60 overflow-y-auto">
                      {REGION_OPTIONS.map((option) => (
                        <div
                          key={option.value}
                          className="flex items-center space-x-2 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
                          onClick={() => {
                            if (
                              !createAccountFormData.region.includes(
                                option.value,
                              )
                            ) {
                              toggleRegion(option.value, false);
                              setIsCreateRegionPopoverOpen(false);
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
                {createAccountFormData.region.map((regionValue, index) => (
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
                      onClick={() => toggleRegion(regionValue, false)}
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
