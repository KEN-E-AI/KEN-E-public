// TODO(extensions-prd): stub for Extensions PRD; replace with real implementation
// when the Extensions component ships. Returns no active extensions; provider is a
// pass-through over a static empty value. Preserves the figma-export
// ExtensionsContext shape so consumers (e.g. ExtensionsNavItem hover panel) render
// correctly with the empty state until the real implementation lands.
//
// figma-export reference: docs/figma-export/src/app/contexts/ExtensionsContext.tsx

import { createContext, useContext, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export interface ExtensionConfigStep {
  id: string;
  title: string;
  description: string;
}

export interface ExtensionDefinition {
  id: string;
  slug: string;
  name: string;
  description: string;
  longDescription: string;
  icon: LucideIcon;
  category: string;
  color: string;
  shadow: string;
  rotation: string;
  configSteps: ExtensionConfigStep[];
  source: "official" | "community";
  author?: string;
}

export interface ExtensionInstance {
  extensionId: string;
  activatedAt: Date;
  config: Record<string, unknown>;
}

interface ExtensionsContextValue {
  activeExtensions: Map<string, ExtensionInstance>;
  isActive: (extensionId: string) => boolean;
  activateExtension: (
    extensionId: string,
    config?: Record<string, unknown>,
  ) => void;
  deactivateExtension: (extensionId: string) => void;
  getActiveExtensionDefinitions: () => ExtensionDefinition[];
}

const stubValue: ExtensionsContextValue = {
  activeExtensions: new Map(),
  isActive: () => false,
  activateExtension: () => {},
  deactivateExtension: () => {},
  getActiveExtensionDefinitions: () => [],
};

const ExtensionsContext = createContext<ExtensionsContextValue | null>(null);

export function ExtensionsProvider({ children }: { children: ReactNode }) {
  return (
    <ExtensionsContext.Provider value={stubValue}>
      {children}
    </ExtensionsContext.Provider>
  );
}

export function useExtensions(): ExtensionsContextValue {
  const ctx = useContext(ExtensionsContext);
  if (!ctx) {
    console.warn(
      "useExtensions called outside ExtensionsProvider — returning stub fallback",
    );
    return stubValue;
  }
  return ctx;
}
