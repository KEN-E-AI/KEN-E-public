import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join, relative } from "node:path";

// --color-text-tertiary fails AA in light mode (~2.475:1 on bg-primary) and
// is formally exempt — see accessibility-baseline.md §Exemptions. Usage is
// strictly limited to decorative or disabled text (timestamps, secondary
// metadata, placeholder/disabled states in form primitives, dim icons).
//
// This audit is the runtime enforcement of that exemption: any new file that
// applies `text-tertiary` (Tailwind class) or `text-[var(--color-text-tertiary)]`
// (arbitrary value) must be added to ALLOWED_FILES below with a one-word
// rationale tag, OR the offending line must carry `// allow-text-tertiary:
// <reason>` as a per-line escape hatch.
//
// `.test.tsx` / `.test.ts` files are excluded — tests can legitimately reference
// the class string in assertions without it appearing in shipped UI.

const FRONTEND_SRC = resolve(__dirname, "..");
const AUDITED_DIRS = [
  resolve(FRONTEND_SRC, "components"),
  resolve(FRONTEND_SRC, "pages"),
];

// File-level allowlist. Path is relative to frontend/src (POSIX separators).
// Tag in the comment is a short rationale category.
const ALLOWED_FILES = new Set<string>([
  // shadcn/ui primitives — placeholder, disabled-state, and dim-icon usage
  "components/ui/accordion.tsx",
  "components/ui/alert-dialog.tsx",
  "components/ui/breadcrumb.tsx",
  "components/ui/button.tsx",
  "components/ui/calendar.tsx",
  "components/ui/chart.tsx",
  "components/ui/command.tsx",
  "components/ui/context-menu.tsx",
  "components/ui/dialog.tsx",
  "components/ui/drawer.tsx",
  "components/ui/dropdown-menu.tsx",
  "components/ui/form.tsx",
  "components/ui/input.tsx",
  "components/ui/menubar.tsx",
  "components/ui/select.tsx",
  "components/ui/sheet.tsx",
  "components/ui/sonner.tsx",
  "components/ui/table.tsx",
  "components/ui/tabs.tsx",
  "components/ui/textarea.tsx",
  "components/ui/toggle.tsx",

  // admin — empty-state secondary message in the Super Admins table
  "components/admin/superAdmins/SuperAdminsTable.tsx",
  // admin — feature-flags table: row timestamps, secondary metadata, empty-state
  "components/admin/featureFlags/FlagTable.tsx",
  // admin — feature-flags create/edit drawer: form-field descriptions
  "components/admin/featureFlags/FlagEditDrawer.tsx",
  // admin — feature-flags targeting editor: field labels + slider helper text
  "components/admin/featureFlags/TargetingRulesEditor.tsx",
  // admin — feature-flags audit list: empty-state copy, row timestamps, diff summary
  "components/admin/featureFlags/FlagAuditList.tsx",

  // chat — timestamps and captions per accessibility-baseline.md §Exemptions.
  // ArtifactBlock and ThinkingBlock are 1:1 ports of docs/figma-export and use
  // text-tertiary for secondary captions (filename helper, reasoning summary,
  // chevron, "Analyzing..." placeholder) — keeping the export alignment per
  // frontend/src/components/CLAUDE.md.
  "components/chat/ArtifactBlock.tsx",
  "components/chat/ChatInterface.tsx",
  "components/chat/SessionsSidebar.tsx",
  "components/chat/ThinkingBlock.tsx",

  // layout — secondary metadata, breadcrumb separators, inactive-link tertiary state
  "components/layout/AccountSwitcher.tsx",
  "components/layout/ExtensionsNavItem.tsx",
  "components/layout/LayoutC.tsx",
  "components/layout/ProfileMenu.tsx",

  // workflows pages — schedule/last-run metadata, DAG placeholder help text, empty-state dim icon + description
  "pages/workflows/AutomationDetailsPage.tsx",

  // dev preview — renders every primitive intentionally
  "pages/__dev__/DesignSystemPreview.tsx",

  // ─── Grandfathered (pre-existing usage) ─────────────────────────────────
  // The cd_pipeline / pr-checks Cloud Build triggers historically excluded
  // `frontend/**` from `included_files`, so this audit never actually ran on
  // PRs touching these files. When the trigger filter was widened (see
  // `deployment/terraform/build_triggers.tf`), 403 violations across 104 files
  // surfaced in one go. All entries below were spot-classified against the
  // spec exemption (decorative / secondary / helper / icon / loading / pill /
  // disabled-state / flow-node / wizard-summary). Each group's comment is the
  // dominant rationale for that subtree.

  // auth — captcha helper text, loading state on the protected-route gate
  "components/auth/ProtectedRoute.tsx",
  "components/auth/ReCaptcha.tsx",
  "components/auth/ReCaptchaV3.tsx",

  // dashboard — section-label headers (uppercase tracking-wide), edit-modal helper text, snapshot captions, dim icons
  "components/dashboard/AnalysisSection.tsx",
  "components/dashboard/ChannelControls.tsx",
  "components/dashboard/ChannelControlsSnapshot.tsx",
  "components/dashboard/EditChannelsModal.tsx",
  "components/dashboard/EditObjectivesModal.tsx",
  "components/dashboard/EditStepsModal.tsx",
  "components/dashboard/EditTacticsModal.tsx",
  "components/dashboard/MetricCard.tsx",
  "components/dashboard/RecommendationsSection.tsx",
  "components/dashboard/SupportingMetricsSection.tsx",

  // flow-node graphs — secondary descriptions inside competitor/customer/product/SWOT/strategy node cards
  "components/competitors/CompetitorFlowNodes.tsx",
  "components/customers/CustomerFlowNodes.tsx",
  "components/marketing/StrategyFlowNodes.tsx",
  "components/products/ProductFlowNodes.tsx",
  "components/swot/SwotFlowNodes.tsx",

  // entity management — empty-state and helper text on competitor/customer/product/SWOT list surfaces
  "components/competitors/CompetitorsManagement.tsx",
  "components/competitors/modals/CompetitorModal.tsx",
  "components/competitors/modals/ValuePropositionModal.tsx",
  "components/customers/CustomerProfilesManagement.tsx",
  "components/products/ProductCategoriesManagement.tsx",
  "components/swot/SwotManagement.tsx",

  // home — chat-area icon-only buttons (hover lifts to primary)
  "components/home/HomeChatArea.tsx",
  "components/home/MessageContent.tsx",

  // integrations — Google Analytics setup loading spinners and helper copy
  "components/integrations/GoogleAnalyticsManage.tsx",
  "components/integrations/GoogleAnalyticsOAuth.tsx",
  "components/integrations/GoogleAnalyticsPropertySelector.tsx",
  "components/integrations/GoogleAnalyticsSetup.tsx",

  // knowledge-base / knowledge-graph — list captions, empty states, sidesheet metadata
  "components/knowledge-base/ActivitiesPage.tsx",
  "components/knowledge-base/MetricsPage.tsx",
  "components/knowledge-graph/core/EmptyState.tsx",
  "components/knowledge-graph/core/HorizontalScrollList.tsx",
  "components/knowledge-graph/item-card/HorizontalScrollItem.tsx",
  "components/knowledge-graph/side-sheet/SideSheetNestedList.tsx",

  // layout — settings shell back-link button and breadcrumb separators
  "components/layout/SettingsLayout.tsx",

  // marketing funnel — secondary descriptions inside funnel stages
  "components/marketing/MarketingFunnelVisualization.tsx",
  "components/marketing/MiniMarketingFunnel.tsx",

  // notifications — secondary metadata, "Coming Soon" pill, hover-tertiary on disabled controls
  "components/notifications/NotificationHandler.tsx",
  "components/notifications/NotificationPreferences.tsx",
  "components/notifications/NotificationSidebar.tsx",

  // settings forms — secondary metadata, helper text, scope tooltips, status badges, validation surfaces
  "components/settings/AccountAccessSettings.tsx",
  "components/settings/AccountCreationWizard.tsx",
  "components/settings/AccountIntegrationsSettings.tsx",
  "components/settings/AccountMarketingSettings.tsx",
  "components/settings/AccountPerformanceSettings.tsx",
  "components/settings/AccountPrivacySettings.tsx",
  "components/settings/AccountProfileSettings.tsx",
  "components/settings/TestNotificationSection.tsx",
  "components/settings/admin/IndustryKeywordsSettings.tsx",
  "components/settings/enhanced/EnhancedEntitySelector.tsx",
  "components/settings/guidance/AdvancedSettingsAccordion.tsx",
  "components/settings/guidance/CrossReferenceSystem.tsx",
  "components/settings/guidance/EnhancedFormField.tsx",
  "components/settings/guidance/HierarchicalSettings.tsx",
  "components/settings/guidance/PermissionAwareContainer.tsx",
  "components/settings/guidance/ScopeBadge.tsx",
  "components/settings/guidance/ScopeTooltip.tsx",
  "components/settings/status/ConfigurationStatusBadge.tsx",
  "components/settings/status/RequiredIndicator.tsx",
  "components/settings/status/UnsavedChangesIndicator.tsx",

  // settings wizard — value summary on confirm step, helper text under step prompts
  "components/settings/wizard/WizardStep1BasicInfo.tsx",
  "components/settings/wizard/WizardStep2MarketingChannels.tsx",
  "components/settings/wizard/WizardStep2MarketingChannelsImproved.tsx",
  "components/settings/wizard/WizardStep2TemplateSelection.tsx",
  "components/settings/wizard/WizardStep3ProductIntegrations.tsx",
  "components/settings/wizard/WizardStep3ProductIntegrationsImproved.tsx",
  "components/settings/wizard/WizardStep5Confirm.tsx",
  "components/settings/wizard/WizardStep5ConfirmImproved.tsx",

  // shared UI primitives (non-shadcn) — helper text, dim icons, validation captions
  "components/ui/ProductIntegrationsEditor.tsx",
  "components/ui/ProductIntegrationsSelector.tsx",
  "components/ui/ValidationAlert.tsx",
  "components/ui/ValidationSummary.tsx",
  "components/ui/entity-selector.tsx",
  "components/ui/file-upload.tsx",

  // ErrorBoundary — Component-Stack debug details + post-action recovery hint.
  // NOTE: line 108 (the body paragraph in the error card) is borderline; the
  // gate's exemption envelope assumes decorative / secondary text, and a body
  // paragraph in the user-visible error UI sits closer to primary content.
  // Recoloring requires a Figma-export update (see docs/figma-export/), so
  // it's deferred — flag for follow-up review.
  "components/ErrorBoundary.tsx",

  // pages — back-link buttons, empty-state messages, page-level descriptions, dim metadata
  "pages/Chat.tsx",
  "pages/AccountSettings.tsx",
  "pages/AccountSettingsPage.tsx",
  "pages/AnalysisReport.tsx",
  "pages/Campaigns.tsx",
  "pages/Customers.tsx",
  "pages/Index.tsx",
  "pages/Insights.tsx",
  "pages/Knowledge.tsx",
  "pages/KnowledgeAccount.tsx",
  "pages/KnowledgeActivities.tsx",
  "pages/KnowledgeBrand.tsx",
  "pages/KnowledgeCompetitors.tsx",
  "pages/KnowledgeCustomers.tsx",
  "pages/KnowledgeMetrics.tsx",
  "pages/KnowledgeStrategy.tsx",
  "pages/Performance.tsx",
  "pages/Products.tsx",
  "pages/Recommendations.tsx",
  "pages/Reports.tsx",
  "pages/Simulations.tsx",
  "pages/UserSettings.tsx",
  "pages/components/AccountsManagement.tsx",
  "pages/components/BillingSection.tsx",
  "pages/components/DangerZone.tsx",
  "pages/components/OrganizationForm.tsx",
  "pages/components/SubscriptionCard.tsx",
  "pages/components/TeamManagement.tsx",
]);

const PER_LINE_ANNOTATION = "allow-text-tertiary";
// Use look-arounds (rather than \b) so the rule matches `text-tertiary` exactly
// and does NOT misfire on hypothetical Tailwind variants like `text-tertiary-50`
// or hyphenated identifiers. `\b` treats `-` as a non-word boundary, so
// `\btext-tertiary\b` would still match inside `text-tertiary-50`.
const TARGET_PATTERNS = [
  /(?<![\w-])text-tertiary(?![\w-])/, // tailwind shorthand
  /text-\[var\(--color-text-tertiary\)\]/, // arbitrary value
];

function getAllSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      files.push(...getAllSourceFiles(full));
    } else if (
      (entry.endsWith(".tsx") || entry.endsWith(".ts")) &&
      !entry.endsWith(".test.tsx") &&
      !entry.endsWith(".test.ts") &&
      !entry.endsWith(".spec.tsx") &&
      !entry.endsWith(".spec.ts")
    ) {
      files.push(full);
    }
  }
  return files;
}

function lineMatchesTarget(line: string): boolean {
  // Strip line comments so a comment that mentions `text-tertiary` (e.g. a
  // migration TODO or rationale note) does not falsely trigger the gate.
  // Match `//` only when preceded by whitespace or line-start so URLs like
  // `https://docs.example.com` are preserved (otherwise we'd silently erase
  // the className that follows the URL on the same line — a false negative).
  // Block comments / JSX comments are rare on a single class-applying line;
  // the per-line `// allow-text-tertiary` escape hatch handles edge cases.
  const codeOnly = line.replace(/(^|\s)\/\/.*$/, "$1");
  return TARGET_PATTERNS.some((re) => re.test(codeOnly));
}

function lineHasAllowAnnotation(line: string, prevLine: string): boolean {
  return (
    line.includes(PER_LINE_ANNOTATION) || prevLine.includes(PER_LINE_ANNOTATION)
  );
}

describe("text-tertiary usage audit", () => {
  const allFiles = AUDITED_DIRS.flatMap(getAllSourceFiles);

  it("audited directories contain source files (guards against directory rename)", () => {
    // Floor pegged near current count (~247). A loose floor (e.g. >50) would
    // let a developer accidentally delete ~80% of the UI tree before the
    // guard fires; the audit would then report zero violations because no
    // files containing text-tertiary were scanned.
    expect(allFiles.length).toBeGreaterThan(200);
  });

  const violations: string[] = [];

  for (const file of allFiles) {
    // .replace(/\\/g, ...) keeps ES2020-lib compatibility (no replaceAll).
    const rel = relative(FRONTEND_SRC, file).replace(/\\/g, "/");
    if (ALLOWED_FILES.has(rel)) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    lines.forEach((line, idx) => {
      if (!lineMatchesTarget(line)) return;
      const prev = idx > 0 ? lines[idx - 1] : "";
      if (lineHasAllowAnnotation(line, prev)) return;
      violations.push(
        `${rel}:${idx + 1} — text-tertiary used outside ALLOWED_FILES with no \`${PER_LINE_ANNOTATION}\` annotation`,
      );
    });
  }

  it("no text-tertiary in non-allowlisted files (without per-line annotation)", () => {
    expect(violations, violations.join("\n")).toHaveLength(0);
  });
});
