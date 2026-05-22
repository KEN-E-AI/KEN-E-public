import { useAuth } from "@/contexts/AuthContext";
import { getTemplateById } from "@/data/accountTemplates";

export interface SmartDefaultResult {
  value: any;
  inheritedFrom: "organization" | "account" | "user" | "template" | "system";
  canOverride: boolean;
  source?: string;
}

export const useSmartDefaults = (
  scope: "organization" | "account" | "user",
) => {
  const { selectedOrgAccount, user, orgMetadata, accountMetadata } = useAuth();

  // Helper function to get template information
  const getTemplateInfo = (setting: string) => {
    const templateId = accountMetadata?.template_id || orgMetadata?.template_id;
    const template = templateId ? getTemplateById(templateId) : null;
    // AccountTemplate only exposes `recommendedSettings`. A previous
    // `defaultSettings` fallback referenced a field that never existed on
    // the type; removed.
    const templateDefault = template?.recommendedSettings?.[
      setting as keyof typeof template.recommendedSettings
    ];

    return { template, templateDefault };
  };

  // Helper function to create a SmartDefaultResult
  const createResult = (
    value: any,
    inheritedFrom: SmartDefaultResult["inheritedFrom"],
    source: string,
  ): SmartDefaultResult => ({
    value,
    inheritedFrom,
    canOverride: true,
    source,
  });

  // Helper function to resolve organization scope
  const resolveOrganizationScope = (
    setting: string,
    fallback?: any,
  ): SmartDefaultResult => {
    const currentOrg = orgMetadata || {};
    const { template, templateDefault } = getTemplateInfo(setting);

    if (currentOrg[setting]) {
      return createResult(
        currentOrg[setting],
        "organization",
        "Organization settings",
      );
    }

    if (templateDefault) {
      return createResult(
        templateDefault,
        "template",
        `${template?.name} template`,
      );
    }

    return createResult(fallback, "system", "System default");
  };

  // Helper function to resolve account scope
  const resolveAccountScope = (
    setting: string,
    fallback?: any,
  ): SmartDefaultResult => {
    const currentOrg = orgMetadata || {};
    const currentAccount = accountMetadata || {};
    const { template, templateDefault } = getTemplateInfo(setting);

    if (currentAccount[setting]) {
      return createResult(
        currentAccount[setting],
        "account",
        "Account settings",
      );
    }

    if (currentOrg[setting]) {
      return createResult(
        currentOrg[setting],
        "organization",
        "Organization settings",
      );
    }

    if (templateDefault) {
      return createResult(
        templateDefault,
        "template",
        `${template?.name} template`,
      );
    }

    return createResult(fallback, "system", "System default");
  };

  // Helper function to resolve user scope
  const resolveUserScope = (
    setting: string,
    fallback?: any,
  ): SmartDefaultResult => {
    const currentOrg = orgMetadata || {};
    const currentAccount = accountMetadata || {};
    const currentUser = user || {};
    const { template, templateDefault } = getTemplateInfo(setting);

    // User type doesn't declare settings/preferences fields, but the runtime
    // shape carries them when populated from the backend profile blob.
    const userWithPrefs = currentUser as {
      settings?: Record<string, unknown>;
      preferences?: Record<string, unknown>;
    };
    const userValue =
      userWithPrefs.settings?.[setting] || userWithPrefs.preferences?.[setting];
    if (userValue) {
      return createResult(userValue, "user", "User preferences");
    }

    if (currentAccount[setting]) {
      return createResult(
        currentAccount[setting],
        "account",
        "Account settings",
      );
    }

    if (currentOrg[setting]) {
      return createResult(
        currentOrg[setting],
        "organization",
        "Organization settings",
      );
    }

    if (templateDefault) {
      return createResult(
        templateDefault,
        "template",
        `${template?.name} template`,
      );
    }

    return createResult(fallback, "system", "System default");
  };

  const getDefaultValue = (
    setting: string,
    fallback?: any,
  ): SmartDefaultResult => {
    switch (scope) {
      case "organization":
        return resolveOrganizationScope(setting, fallback);
      case "account":
        return resolveAccountScope(setting, fallback);
      case "user":
        return resolveUserScope(setting, fallback);
      default:
        return createResult(fallback, "system", "System default");
    }
  };

  const getInheritanceChain = (setting: string): SmartDefaultResult[] => {
    const chain: SmartDefaultResult[] = [];

    // Helper function to add to chain if value exists
    const addToChainIfExists = (
      value: any,
      inheritedFrom: SmartDefaultResult["inheritedFrom"],
      source: string,
    ) => {
      if (value !== undefined && value !== null) {
        chain.push(createResult(value, inheritedFrom, source));
      }
    };

    // User level (see comment on the matching cast in resolveAccountScope).
    const userWithPrefs = user as
      | {
          settings?: Record<string, unknown>;
          preferences?: Record<string, unknown>;
        }
      | null;
    const userValue =
      userWithPrefs?.settings?.[setting] ||
      userWithPrefs?.preferences?.[setting];
    addToChainIfExists(userValue, "user", "User preferences");

    // Account level
    addToChainIfExists(
      accountMetadata?.[setting],
      "account",
      "Account settings",
    );

    // Organization level
    addToChainIfExists(
      orgMetadata?.[setting],
      "organization",
      "Organization settings",
    );

    // Template level - only add if no organization/account value exists
    if (!orgMetadata?.[setting] && !accountMetadata?.[setting]) {
      const { template, templateDefault } = getTemplateInfo(setting);
      addToChainIfExists(
        templateDefault,
        "template",
        `${template?.name} template`,
      );
    }

    return chain;
  };

  const getSuggestions = (setting: string): string[] => {
    const { template } = getTemplateInfo(setting);

    // Setting-specific suggestions
    const suggestionMap: Record<string, string[]> = {
      timezone: [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
      ],
      language: ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
      theme: ["light", "dark", "auto"],
      industry: [
        "Technology",
        "Healthcare",
        "Finance",
        "Education",
        "Retail",
        "Manufacturing",
        "Professional Services",
        "Non-Profit",
      ],
      status: ["Active", "Inactive", "Setup", "Paused"],
      // Days, stringified so the array type matches the surrounding
      // `Record<string, string[]>` suggestion-map contract.
      data_retention: ["30", "90", "180", "365", "730", "1825"],
    };

    // Template-based suggestions
    const templateSuggestions = {
      objectives: template?.defaultObjectives || [],
      channels: template?.defaultChannels || [],
      kpis: template?.defaultKPIs || [],
    };

    return templateSuggestions[setting] || suggestionMap[setting] || [];
  };

  const getRecommendation = (
    setting: string,
  ): { value: any; reason: string } | null => {
    const { template } = getTemplateInfo(setting);

    // Context-based recommendations (prioritized)
    const contextRecommendations = {
      timezone: orgMetadata?.timezone
        ? {
            value: orgMetadata.timezone,
            reason: "Matches your organization's timezone",
          }
        : null,
      language: user?.preferences?.language
        ? {
            value: user.preferences.language,
            reason: "Matches your user preference",
          }
        : null,
    };

    // Check context-based recommendations first
    if (contextRecommendations[setting]) {
      return contextRecommendations[setting];
    }

    // Template-based recommendations (fallback)
    if (template?.recommendedSettings?.[setting]) {
      return {
        value: template.recommendedSettings[setting],
        reason: `Recommended for ${template.name} accounts`,
      };
    }

    return null;
  };

  return {
    getDefaultValue,
    getInheritanceChain,
    getSuggestions,
    getRecommendation,
  };
};
