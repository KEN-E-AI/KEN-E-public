// Tooltip and Help System
export { ScopeTooltip, ScopeHelpIcon } from "./ScopeTooltip";

// Smart Defaults
export { useSmartDefaults } from "./useSmartDefaults";
export type { SmartDefaultResult } from "./useSmartDefaults";

// Scope Indicators
export { ScopeBadge, ScopeIndicator, InheritanceChain } from "./ScopeBadge";

// Enhanced Form Components
export {
  EnhancedFormField,
  SimpleEnhancedFormField,
} from "./EnhancedFormField";

// Progressive Disclosure
export {
  AdvancedSettingsAccordion,
  SettingsGroup,
  ProgressiveDisclosure,
} from "./AdvancedSettingsAccordion";

// Cross-Reference System
export {
  CrossReferenceIndicator,
  DependencyChain,
  getRelatedSettings,
} from "./CrossReferenceSystem";

// Hierarchical Layout
export {
  HierarchicalSettings,
  SettingsSection,
  ScopeNavigation,
} from "./HierarchicalSettings";

// Phase 6: Permission Management
export {
  PermissionAwareContainer,
  PermissionCheck,
  ConditionalPermission,
} from "./PermissionAwareContainer";

// Phase 6: Contextual Actions
export {
  ContextualActionBar,
  QuickActionBar,
  getOrganizationActions,
  getAccountActions,
  getUserActions,
  type ContextualActionType,
} from "./ContextualActionBar";

// Phase 6: Enhanced Components
export {
  EnhancedEntitySelector,
  ContextSwitcher,
} from "../enhanced/EnhancedEntitySelector";

// Phase 6: Status Indicators
export {
  ConfigurationStatusBadge,
  ConfigurationOverview,
  type ConfigurationStatus,
} from "../status/ConfigurationStatusBadge";

export {
  RequiredIndicator,
  FieldRequiredIndicator,
  RequiredFieldsOverview,
} from "../status/RequiredIndicator";

export {
  UnsavedChangesIndicator,
  AutoSaveIndicator,
  FormStateIndicator,
} from "../status/UnsavedChangesIndicator";
