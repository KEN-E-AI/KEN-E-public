import { useState } from "react";
import { Link, ExternalLink, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScopeBadge } from "./ScopeBadge";

interface RelatedSetting {
  id: string;
  name: string;
  description: string;
  scope: "organization" | "account" | "user";
  route?: string;
  section?: string;
  relationship: "depends_on" | "affects" | "related_to" | "inherits_from";
  impact?: "high" | "medium" | "low";
}

interface CrossReferenceIndicatorProps {
  setting: string;
  relatedSettings: RelatedSetting[];
  className?: string;
}

export const CrossReferenceIndicator = ({
  setting,
  relatedSettings,
  className,
}: CrossReferenceIndicatorProps) => {
  const [showReferences, setShowReferences] = useState(false);

  if (relatedSettings.length === 0) return null;

  const getRelationshipIcon = (relationship: string) => {
    switch (relationship) {
      case "depends_on":
        return "🔗";
      case "affects":
        return "⚡";
      case "related_to":
        return "🔄";
      case "inherits_from":
        return "⬇️";
      default:
        return "🔗";
    }
  };

  const getRelationshipText = (relationship: string) => {
    switch (relationship) {
      case "depends_on":
        return "Depends on";
      case "affects":
        return "Affects";
      case "related_to":
        return "Related to";
      case "inherits_from":
        return "Inherits from";
      default:
        return "Related to";
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case "high":
        return "text-red-600 bg-red-50 border-red-200";
      case "medium":
        return "text-brand-dark-blue bg-brand-yellow/20 border-brand-yellow/40";
      case "low":
        return "text-brand-dark-blue bg-brand-light-green/20 border-brand-light-green/40";
      default:
        return "text-[var(--color-text-tertiary)] bg-[var(--color-bg-secondary)] border-[var(--color-border-default)]";
    }
  };

  return (
    <Dialog open={showReferences} onOpenChange={setShowReferences}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-brand-medium-blue hover:text-brand-dark-blue h-6 px-2"
        >
          <Link className="h-3 w-3 mr-1" />
          <span className="text-xs">Related ({relatedSettings.length})</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Link className="h-5 w-5" />
            Related Settings
          </DialogTitle>
          <DialogDescription>
            Settings that are connected to <strong>{setting}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 max-h-96 overflow-y-auto">
          {relatedSettings.map((related) => (
            <div
              key={related.id}
              className="border rounded-lg p-4 hover:bg-[var(--color-bg-secondary)] transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-sm">{related.name}</h4>
                    <ScopeBadge scope={related.scope} size="sm" />
                  </div>
                  <p className="text-sm text-[var(--color-text-tertiary)] mb-2">
                    {related.description}
                  </p>
                </div>
                {related.route && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-2 h-6 px-2"
                    onClick={() => {
                      // Navigate to the related setting
                      // This would be implemented based on your routing system
                      setShowReferences(false);
                    }}
                  >
                    <ExternalLink className="h-3 w-3" />
                  </Button>
                )}
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--color-text-tertiary)]">
                    {getRelationshipIcon(related.relationship)}{" "}
                    {getRelationshipText(related.relationship)}
                  </span>
                  {related.section && (
                    <Badge variant="outline" className="text-xs">
                      {related.section}
                    </Badge>
                  )}
                </div>

                {related.impact && (
                  <Badge
                    variant="outline"
                    className={`text-xs ${getImpactColor(related.impact)}`}
                  >
                    {related.impact} impact
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t pt-4">
          <p className="text-xs text-[var(--color-text-tertiary)] text-center">
            Changes to related settings may affect the behavior of this setting.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

interface DependencyChainProps {
  dependencies: RelatedSetting[];
  className?: string;
}

export const DependencyChain = ({
  dependencies,
  className,
}: DependencyChainProps) => {
  if (dependencies.length === 0) return null;

  return (
    <div
      className={`border rounded-lg p-3 bg-brand-light-blue/20 ${className}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Link className="h-4 w-4 text-brand-medium-blue" />
        <span className="text-sm font-medium text-brand-dark-blue">
          Dependencies
        </span>
      </div>

      <div className="space-y-2">
        {dependencies.map((dep, index) => (
          <div key={dep.id} className="flex items-center gap-2 text-sm">
            <ScopeBadge scope={dep.scope} size="sm" />
            <span className="text-brand-dark-blue">{dep.name}</span>
            {index < dependencies.length - 1 && (
              <ArrowRight className="h-3 w-3 text-brand-light-blue" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Utility function to get related settings for common settings
export const getRelatedSettings = (setting: string): RelatedSetting[] => {
  const relationshipMap: Record<string, RelatedSetting[]> = {
    timezone: [
      {
        id: "organization-timezone",
        name: "Organization Timezone",
        description: "The default timezone for your organization",
        scope: "organization",
        route: "/organization-settings",
        section: "General",
        relationship: "inherits_from",
        impact: "medium",
      },
      {
        id: "campaign-scheduling",
        name: "Campaign Scheduling",
        description: "Campaign start and end times use this timezone",
        scope: "account",
        route: "/account-settings",
        section: "Marketing",
        relationship: "affects",
        impact: "high",
      },
      {
        id: "reporting-timezone",
        name: "Report Timezone",
        description: "All reports and analytics use this timezone",
        scope: "account",
        route: "/account-settings",
        section: "Analytics",
        relationship: "affects",
        impact: "medium",
      },
    ],
    auto_sync: [
      {
        id: "data-retention",
        name: "Data Retention",
        description: "How long synced data is stored",
        scope: "organization",
        route: "/organization-settings",
        section: "Data Management",
        relationship: "related_to",
        impact: "medium",
      },
      {
        id: "integrations",
        name: "Platform Integrations",
        description: "Connected platforms that provide data",
        scope: "account",
        route: "/account-settings",
        section: "Integrations",
        relationship: "depends_on",
        impact: "high",
      },
    ],
    performance_alerts: [
      {
        id: "notification-settings",
        name: "Notification Preferences",
        description: "How you receive alert notifications",
        scope: "user",
        route: "/user-settings",
        section: "Notifications",
        relationship: "depends_on",
        impact: "medium",
      },
      {
        id: "kpi-thresholds",
        name: "KPI Thresholds",
        description: "Performance thresholds that trigger alerts",
        scope: "account",
        route: "/account-settings",
        section: "Performance",
        relationship: "depends_on",
        impact: "high",
      },
    ],
    industry: [
      {
        id: "account-templates",
        name: "Account Templates",
        description: "Industry-specific templates and defaults",
        scope: "account",
        route: "/account-settings",
        section: "Templates",
        relationship: "affects",
        impact: "high",
      },
      {
        id: "benchmark-data",
        name: "Industry Benchmarks",
        description: "Comparative performance data for your industry",
        scope: "account",
        route: "/account-settings",
        section: "Analytics",
        relationship: "affects",
        impact: "medium",
      },
    ],
  };

  return relationshipMap[setting] || [];
};
