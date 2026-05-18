import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Zap,
  Globe,
  AlertTriangle,
  Trash2,
  DollarSign,
  ChevronDown,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceOptions } from "@/hooks/useWorkspaceOptions";
import { useToast } from "@/hooks/use-toast";
import {
  getAccountById,
  updateAccount,
  deleteAccount,
  moveAccount,
} from "@/data/organizationApi";
import { INDUSTRY_OPTIONS, TIMEZONE_OPTIONS } from "@/data/organizationTypes";
import { MARKETING_CHANNELS } from "@/data/marketingChannels";
import type { Account } from "@/data/organizationTypes";
import type { AccountId } from "@/lib/branded-types";

type AccountSettingsTabsProps = {
  accountId: AccountId;
};

// Customer Region is a multi-select: an account can serve several geographic
// markets. Values match the account-creation wizard's region scheme. "Global"
// is mutually exclusive with the specific regions (see toggleCustomerRegion).
const GLOBAL_REGION = "Global";

const CUSTOMER_REGION_OPTIONS = [
  { value: GLOBAL_REGION, label: "Global" },
  { value: "NA", label: "North America" },
  { value: "EMEA", label: "Europe, Middle East & Africa" },
  { value: "JAPAC", label: "Japan & Asia Pacific" },
  { value: "LAC", label: "Latin America & Caribbean" },
];

const regionLabel = (value: string): string =>
  CUSTOMER_REGION_OPTIONS.find((option) => option.value === value)?.label ??
  value;

const DATA_REGION_OPTIONS = [
  { value: "US", label: "United States" },
  { value: "EU", label: "Europe" },
];

// Figma names the integration cards explicitly; connection state is reflected
// from the account's product_integrations list. OAuth itself lives on the
// dedicated /settings/integrations page.
const KNOWN_INTEGRATIONS = ["Google Analytics", "Google Ads", "Meta Ads"];

type EditableAccount = {
  account_name: string;
  industry: string;
  estimated_annual_ad_budget: number | null;
  status: string;
  timezone: string;
  data_region: string;
  region: string[];
  websites: string[];
  marketing_channels: string[];
};

const toEditable = (account: Account): EditableAccount => ({
  account_name: account.account_name ?? "",
  industry: account.industry ?? "",
  estimated_annual_ad_budget: account.estimated_annual_ad_budget ?? null,
  status: account.status ?? "active",
  timezone: account.timezone ?? "",
  data_region: account.data_region ?? "",
  region: account.region ?? [],
  websites: account.websites ?? [],
  marketing_channels: account.marketing_channels ?? [],
});

const isActiveStatus = (status: string) => status.toLowerCase() === "active";

/**
 * Toggles a customer region in/out of the selection. "Global" is mutually
 * exclusive with the specific regions: selecting Global clears the rest, and
 * selecting any specific region clears Global — a "Global + North America"
 * selection would be contradictory.
 */
export const toggleCustomerRegion = (
  regions: string[],
  value: string,
): string[] => {
  if (regions.includes(value)) {
    return regions.filter((region) => region !== value);
  }
  if (value === GLOBAL_REGION) {
    return [GLOBAL_REGION];
  }
  return [...regions.filter((region) => region !== GLOBAL_REGION), value];
};

/**
 * Wired account-settings view rendered for /settings/account[/{accountId}].
 *
 * Replaces the previous static Figma mockup: every field now loads from the
 * account record (GET /api/v1/accounts/{id}) and persists via updateAccount.
 */
export function AccountSettingsTabs({ accountId }: AccountSettingsTabsProps) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  // Use the live workspace fetch — not the AuthContext snapshot — so the
  // transfer-org list is complete for super admins.
  const { data: workspaceOptions } = useWorkspaceOptions();

  const [activeTab, setActiveTab] = useState("general");
  const [form, setForm] = useState<EditableAccount | null>(null);
  const [transferTargetOrg, setTransferTargetOrg] = useState("");

  const {
    data: account,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["account", accountId],
    queryFn: () => getAccountById(accountId),
    enabled: Boolean(accountId),
  });

  // Seed the editable form once the account resolves (and whenever it is
  // refetched), so the inputs reflect the persisted record.
  useEffect(() => {
    if (account) setForm(toEditable(account));
  }, [account]);

  const isDirty = useMemo(() => {
    if (!account || !form) return false;
    return JSON.stringify(form) !== JSON.stringify(toEditable(account));
  }, [account, form]);

  const saveMutation = useMutation({
    mutationFn: (updates: EditableAccount) => updateAccount(accountId, updates),
    onSuccess: (updated) => {
      queryClient.setQueryData(["account", accountId], updated);
      queryClient.invalidateQueries({ queryKey: ["workspace-options"] });
      toast({ title: "Account saved" });
    },
    onError: (error: unknown) => {
      toast({
        title: "Couldn't save account",
        description:
          error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    },
  });

  const transferMutation = useMutation({
    mutationFn: (targetOrgId: string) =>
      moveAccount(
        String(account?.organization_id ?? ""),
        accountId,
        targetOrgId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-options"] });
      toast({ title: "Account transferred" });
      navigate("/settings/organization");
    },
    onError: (error: unknown) => {
      toast({
        title: "Couldn't transfer account",
        description:
          error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-options"] });
      toast({ title: "Account deleted" });
      navigate("/settings/organization");
    },
    onError: (error: unknown) => {
      toast({
        title: "Couldn't delete account",
        description:
          error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    },
  });

  if (isLoading || (account && !form)) {
    return (
      <div className="text-center py-8">
        <div className="inline-flex items-center space-x-2">
          <div className="w-4 h-4 border-2 border-[var(--color-violet-500)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--color-text-secondary)]">
            Loading account data...
          </span>
        </div>
      </div>
    );
  }

  if (isError || !account || !form) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted-foreground">
          Unable to load this account. It may have been deleted, or you may not
          have access to it.
        </p>
      </Card>
    );
  }

  const update = <K extends keyof EditableAccount>(
    key: K,
    value: EditableAccount[K],
  ) => setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const toggleMarketingChannel = (channel: string) => {
    update(
      "marketing_channels",
      form.marketing_channels.includes(channel)
        ? form.marketing_channels.filter((c) => c !== channel)
        : [...form.marketing_channels, channel],
    );
  };

  const updateWebsite = (index: number, value: string) =>
    update(
      "websites",
      form.websites.map((w, i) => (i === index ? value : w)),
    );

  const removeWebsite = (index: number) =>
    update(
      "websites",
      form.websites.filter((_, i) => i !== index),
    );

  const handleSave = () => {
    if (!isDirty) return;
    saveMutation.mutate({
      ...form,
      websites: form.websites.map((w) => w.trim()).filter(Boolean),
    });
  };

  const handleTransfer = () => {
    if (!transferTargetOrg) return;
    if (
      !window.confirm(
        "Move this account to a different organization? This cannot be undone.",
      )
    ) {
      return;
    }
    transferMutation.mutate(transferTargetOrg);
  };

  const handleDelete = () => {
    if (
      !window.confirm(
        "Permanently delete this account and all its data? This cannot be undone.",
      )
    ) {
      return;
    }
    deleteMutation.mutate();
  };

  const organizationName =
    (
      workspaceOptions?.orgMetadata?.[String(account.organization_id)] as
        | { organization_name?: string }
        | undefined
    )?.organization_name ?? "Organization";

  const transferOrgOptions = Object.entries(workspaceOptions?.orgMetadata ?? {})
    .filter(([orgId]) => orgId !== String(account.organization_id))
    .map(([orgId, org]) => ({
      orgId,
      name: (org as { organization_name?: string }).organization_name ?? orgId,
    }));

  const showSaveBar = activeTab === "general" || activeTab === "channels";

  return (
    <div>
      <div className="mb-6">
        <button
          type="button"
          onClick={() => navigate("/settings/organization")}
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <Building2 className="size-3.5" />
          <span className="hover:underline">{organizationName}</span>
        </button>
        <h1 className="mt-1">{account.account_name}</h1>
      </div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="general">
            <Building2 className="size-4 mr-2" />
            General
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Zap className="size-4 mr-2" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="channels">
            <Globe className="size-4 mr-2" />
            Channels
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <AlertTriangle className="size-4 mr-2" />
            Advanced
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <div className="space-y-6 max-w-3xl">
            <Card className="p-6">
              <h2 className="mb-4">Account Details</h2>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="account-name">Account Name</Label>
                  <Input
                    id="account-name"
                    placeholder="Account name"
                    className="mt-1.5"
                    value={form.account_name}
                    onChange={(e) => update("account_name", e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">
                    A descriptive name for this marketing account
                  </p>
                </div>
                <div>
                  <Label htmlFor="industry">Industry</Label>
                  <Select
                    value={form.industry}
                    onValueChange={(value) => update("industry", value)}
                  >
                    <SelectTrigger id="industry" className="mt-1.5">
                      <SelectValue placeholder="Select industry..." />
                    </SelectTrigger>
                    <SelectContent>
                      {INDUSTRY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="budget">Annual Advertising Budget</Label>
                  <div className="relative mt-1.5">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                    <Input
                      id="budget"
                      type="number"
                      placeholder="500000"
                      className="pl-9"
                      value={form.estimated_annual_ad_budget ?? ""}
                      onChange={(e) =>
                        update(
                          "estimated_annual_ad_budget",
                          e.target.value === "" ? null : Number(e.target.value),
                        )
                      }
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label htmlFor="account-status">Account Status</Label>
                    <p className="text-sm text-muted-foreground">
                      Active accounts are visible to all team members
                    </p>
                  </div>
                  <Switch
                    id="account-status"
                    checked={isActiveStatus(form.status)}
                    onCheckedChange={(checked) =>
                      update("status", checked ? "active" : "inactive")
                    }
                  />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Regional Settings</h2>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="acct-timezone">Timezone</Label>
                  <Select
                    value={form.timezone}
                    onValueChange={(value) => update("timezone", value)}
                  >
                    <SelectTrigger id="acct-timezone" className="mt-1.5">
                      <SelectValue placeholder="Select timezone..." />
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
                <div>
                  <Label htmlFor="data-region">Data Storage Region</Label>
                  <Select
                    value={form.data_region}
                    onValueChange={(value) => update("data_region", value)}
                  >
                    <SelectTrigger id="data-region" className="mt-1.5">
                      <SelectValue placeholder="Select region..." />
                    </SelectTrigger>
                    <SelectContent>
                      {DATA_REGION_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Where your marketing data is stored for compliance
                  </p>
                </div>
                <div>
                  <Label htmlFor="customer-region">Customer Region</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        id="customer-region"
                        type="button"
                        className="mt-1.5 flex min-h-10 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      >
                        {form.region.length > 0 ? (
                          <span className="flex flex-1 flex-wrap gap-1.5">
                            {form.region.map((value) => (
                              <Badge key={value} variant="secondary">
                                {regionLabel(value)}
                              </Badge>
                            ))}
                          </span>
                        ) : (
                          <span className="flex-1 text-left text-muted-foreground">
                            Select regions...
                          </span>
                        )}
                        <ChevronDown className="size-4 shrink-0 opacity-50" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent
                      align="start"
                      className="w-[var(--radix-popover-trigger-width)] p-1"
                    >
                      {CUSTOMER_REGION_OPTIONS.map((option) => (
                        <label
                          key={option.value}
                          className="flex cursor-pointer items-center gap-2.5 rounded-sm px-2 py-2 text-sm hover:bg-accent"
                        >
                          <Checkbox
                            checked={form.region.includes(option.value)}
                            onCheckedChange={() =>
                              update(
                                "region",
                                toggleCustomerRegion(form.region, option.value),
                              )
                            }
                          />
                          {option.label}
                        </label>
                      ))}
                    </PopoverContent>
                  </Popover>
                  <p className="text-xs text-muted-foreground mt-1.5">
                    The geographic markets your customers are in
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="integrations">
          <div className="space-y-6">
            <div>
              <h2 className="mb-1">Active Integrations</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Connect your marketing tools to enable AI-powered automation
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {KNOWN_INTEGRATIONS.map((name) => {
                  const connected = (account.product_integrations ?? []).some(
                    (p) => p.toLowerCase() === name.toLowerCase(),
                  );
                  return (
                    <Card key={name} className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{name}</p>
                          <div
                            className={
                              connected
                                ? "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full mt-1 bg-[var(--color-success-bg)]"
                                : "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full mt-1 bg-[var(--color-error-bg)]"
                            }
                          >
                            <span
                              className={
                                connected
                                  ? "size-1.5 rounded-full bg-[var(--color-success)]"
                                  : "size-1.5 rounded-full bg-[var(--color-error)]"
                              }
                            />
                            <span
                              className={
                                connected
                                  ? "text-xs font-semibold text-[var(--color-success-text)]"
                                  : "text-xs font-semibold text-[var(--color-error-text)]"
                              }
                            >
                              {connected ? "Connected" : "Not Connected"}
                            </span>
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate("/settings/integrations")}
                        >
                          Configure
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground mt-4">
                Connection status reflects this account&apos;s integrations.
                Connect or disconnect tools from the Integrations page.
              </p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="channels">
          <div className="space-y-6 max-w-3xl">
            <Card className="p-6">
              <h2 className="mb-4">Company Websites</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Domains owned by your company
              </p>
              <div className="space-y-3 mb-4">
                {form.websites.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No websites added yet.
                  </p>
                )}
                {form.websites.map((domain, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Globe className="size-4 text-muted-foreground shrink-0" />
                    <Input
                      value={domain}
                      placeholder="example.com"
                      onChange={(e) => updateWebsite(index, e.target.value)}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Remove website"
                      onClick={() => removeWebsite(index)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => update("websites", [...form.websites, ""])}
              >
                Add Website
              </Button>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Marketing Channels</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Select the channels you use for marketing
              </p>
              <div className="space-y-3">
                {MARKETING_CHANNELS.map((channel) => (
                  <div
                    key={channel}
                    className="flex items-center justify-between"
                  >
                    <Label htmlFor={`channel-${channel}`}>{channel}</Label>
                    <Switch
                      id={`channel-${channel}`}
                      checked={form.marketing_channels.includes(channel)}
                      onCheckedChange={() => toggleMarketingChannel(channel)}
                    />
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="advanced">
          <div className="space-y-6 max-w-3xl">
            <Card className="p-6 border-amber-500/50">
              <div className="flex items-start gap-3 mb-4">
                <AlertTriangle className="size-5 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <h2 className="mb-1 text-amber-500">Transfer Account</h2>
                  <p className="text-sm text-muted-foreground">
                    Move this account to a different organization. This cannot
                    be undone.
                  </p>
                </div>
              </div>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="target-org">Target Organization</Label>
                  <Select
                    value={transferTargetOrg}
                    onValueChange={setTransferTargetOrg}
                  >
                    <SelectTrigger id="target-org" className="mt-1.5">
                      <SelectValue placeholder="Select organization..." />
                    </SelectTrigger>
                    <SelectContent>
                      {transferOrgOptions.length === 0 && (
                        <SelectItem value="__none" disabled>
                          No other organizations available
                        </SelectItem>
                      )}
                      {transferOrgOptions.map((org) => (
                        <SelectItem key={org.orgId} value={org.orgId}>
                          {org.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  disabled={!transferTargetOrg || transferMutation.isPending}
                  onClick={handleTransfer}
                >
                  {transferMutation.isPending
                    ? "Transferring..."
                    : "Transfer Account"}
                </Button>
              </div>
            </Card>

            <Card className="p-6 border-destructive/50">
              <div className="flex items-start gap-3 mb-4">
                <Trash2 className="size-5 text-destructive shrink-0 mt-0.5" />
                <div>
                  <h2 className="mb-1 text-destructive">Delete Account</h2>
                  <p className="text-sm text-muted-foreground">
                    Permanently delete this account and all its data. This
                    action cannot be undone.
                  </p>
                </div>
              </div>
              <Button
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={handleDelete}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete Account"}
              </Button>
            </Card>
          </div>
        </TabsContent>

        {showSaveBar && (
          <div className="flex items-center justify-end gap-3 mt-6 max-w-3xl">
            {isDirty && (
              <span className="text-sm text-muted-foreground">
                You have unsaved changes
              </span>
            )}
            <Button
              disabled={!isDirty || saveMutation.isPending}
              onClick={handleSave}
            >
              {saveMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </Tabs>
    </div>
  );
}
