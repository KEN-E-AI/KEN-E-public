import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ScopeTooltipProps {
  scope: "organization" | "account" | "user";
  setting: string;
  children: React.ReactNode;
}

interface TooltipContentData {
  title: string;
  description: string;
  scopeExplanation: string;
  location?: string;
}

const getTooltipContent = (
  scope: string,
  setting: string,
): TooltipContentData => {
  const baseContent = {
    organization: {
      title: "Organization Setting",
      description:
        "This setting applies to your entire organization and affects all accounts within it.",
      scopeExplanation:
        "Changes here impact all accounts and users in your organization.",
      location: "Settings → Organization Settings",
    },
    account: {
      title: "Account Setting",
      description:
        "This setting applies to this specific account and its associated users.",
      scopeExplanation: "Changes here only affect this account and its users.",
      location: "Settings → Account Settings",
    },
    user: {
      title: "User Setting",
      description:
        "This setting applies only to your user profile and preferences.",
      scopeExplanation: "Changes here only affect your personal experience.",
      location: "Settings → User Settings",
    },
  };

  // Setting-specific overrides
  const settingOverrides: Record<
    string,
    Partial<Record<string, Partial<TooltipContentData>>>
  > = {
    account_name: {
      account: {
        title: "Account Name",
        description:
          "The display name for this marketing account. This helps identify the account in reports and dashboards.",
        scopeExplanation:
          "This name appears in all reports and analytics for this account.",
      },
    },
    industry: {
      account: {
        title: "Industry Setting",
        description:
          "The industry classification affects default templates, KPIs, and benchmark comparisons.",
        scopeExplanation:
          "Industry selection influences recommended marketing channels and performance benchmarks.",
      },
    },
    timezone: {
      organization: {
        title: "Organization Timezone",
        description:
          "The default timezone for all accounts in your organization. Used for scheduling and reporting.",
        scopeExplanation:
          "All accounts inherit this timezone unless overridden at the account level.",
      },
      account: {
        title: "Account Timezone",
        description:
          "The timezone for this specific account. Overrides the organization default.",
        scopeExplanation:
          "Campaign schedules and reports for this account use this timezone.",
      },
    },
    auto_sync: {
      account: {
        title: "Auto-sync Data",
        description:
          "Automatically synchronize data from connected marketing platforms and tools.",
        scopeExplanation:
          "When enabled, data updates automatically from connected integrations.",
      },
    },
    performance_alerts: {
      account: {
        title: "Performance Alerts",
        description:
          "Receive notifications when account performance exceeds or falls below thresholds.",
        scopeExplanation:
          "Alerts help you stay on top of campaign performance changes.",
      },
    },
    data_retention: {
      organization: {
        title: "Data Retention Policy",
        description:
          "How long data is stored before being archived. Affects all accounts in your organization.",
        scopeExplanation:
          "Longer retention periods provide more historical data for analysis.",
      },
    },
    language: {
      user: {
        title: "Interface Language",
        description:
          "Your preferred language for the user interface and communications.",
        scopeExplanation: "This only affects your personal interface language.",
      },
    },
    theme: {
      user: {
        title: "Interface Theme",
        description:
          "Your preferred color scheme and visual theme for the interface.",
        scopeExplanation: "This only affects your personal visual experience.",
      },
    },
  };

  const base = baseContent[scope] || baseContent.organization;
  const override = settingOverrides[setting]?.[scope] || {};

  return {
    ...base,
    ...override,
  };
};

export const ScopeTooltip = ({
  scope,
  setting,
  children,
}: ScopeTooltipProps) => {
  const tooltipContent = getTooltipContent(scope, setting);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <div className="space-y-2">
            <p className="font-medium text-sm">{tooltipContent.title}</p>
            <p className="text-sm text-muted-foreground">
              {tooltipContent.description}
            </p>
            <div className="text-xs text-brand-medium-blue border-t pt-2">
              {tooltipContent.scopeExplanation}
            </div>
            {tooltipContent.location && (
              <div className="text-xs text-[var(--color-text-tertiary)] italic">
                📍 {tooltipContent.location}
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export const ScopeHelpIcon = ({
  scope,
  setting,
}: {
  scope: "organization" | "account" | "user";
  setting: string;
}) => (
  <ScopeTooltip scope={scope} setting={setting}>
    <HelpCircle className="h-4 w-4 text-dashboard-gray-400 cursor-help hover:text-dashboard-gray-600 transition-colors" />
  </ScopeTooltip>
);
