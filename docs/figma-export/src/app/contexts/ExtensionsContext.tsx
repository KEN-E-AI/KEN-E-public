import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import { extensionCatalog, type ExtensionDefinition, type ExtensionInstance } from '../data/extensionRegistry';

interface ExtensionsContextValue {
  activeExtensions: Map<string, ExtensionInstance>;
  isActive: (extensionId: string) => boolean;
  activateExtension: (extensionId: string, config?: Record<string, unknown>) => void;
  deactivateExtension: (extensionId: string) => void;
  getActiveExtensionDefinitions: () => ExtensionDefinition[];
}

const ExtensionsContext = createContext<ExtensionsContextValue | null>(null);

// Seed both extensions as pre-activated so the UI isn't empty on first load
function getInitialExtensions(): Map<string, ExtensionInstance> {
  const stored = (() => {
    try {
      const raw = localStorage.getItem('kene-active-extensions');
      if (raw) return JSON.parse(raw) as Array<[string, ExtensionInstance]>;
    } catch { /* sandbox may block localStorage */ }
    return null;
  })();

  if (stored) {
    return new Map(
      stored.map(([k, v]) => [k, { ...v, activatedAt: new Date(v.activatedAt) }])
    );
  }

  // Default: both extensions pre-activated
  const now = new Date();
  return new Map([
    ['dashboard-creator', { extensionId: 'dashboard-creator', activatedAt: now, config: {} }],
  ]);
}

function persistExtensions(extensions: Map<string, ExtensionInstance>) {
  try {
    localStorage.setItem('kene-active-extensions', JSON.stringify(Array.from(extensions.entries())));
  } catch { /* ignore */ }
}

export function ExtensionsProvider({ children }: { children: ReactNode }) {
  const [activeExtensions, setActiveExtensions] = useState<Map<string, ExtensionInstance>>(getInitialExtensions);

  const isActive = useCallback(
    (extensionId: string) => activeExtensions.has(extensionId),
    [activeExtensions]
  );

  const activateExtension = useCallback(
    (extensionId: string, config: Record<string, unknown> = {}) => {
      setActiveExtensions((prev) => {
        const next = new Map(prev);
        next.set(extensionId, { extensionId, activatedAt: new Date(), config });
        persistExtensions(next);
        return next;
      });
    },
    []
  );

  const deactivateExtension = useCallback(
    (extensionId: string) => {
      setActiveExtensions((prev) => {
        const next = new Map(prev);
        next.delete(extensionId);
        persistExtensions(next);
        return next;
      });
    },
    []
  );

  const getActiveExtensionDefinitions = useCallback(
    () => extensionCatalog.filter((p) => activeExtensions.has(p.id)),
    [activeExtensions]
  );

  const value = useMemo(
    () => ({ activeExtensions, isActive, activateExtension, deactivateExtension, getActiveExtensionDefinitions }),
    [activeExtensions, isActive, activateExtension, deactivateExtension, getActiveExtensionDefinitions]
  );

  return <ExtensionsContext.Provider value={value}>{children}</ExtensionsContext.Provider>;
}

const fallback: ExtensionsContextValue = {
  activeExtensions: new Map(),
  isActive: () => false,
  activateExtension: () => {},
  deactivateExtension: () => {},
  getActiveExtensionDefinitions: () => [],
};

export function useExtensions(): ExtensionsContextValue {
  const ctx = useContext(ExtensionsContext);
  if (!ctx) {
    console.warn('useExtensions called outside ExtensionsProvider – returning fallback');
    return fallback;
  }
  return ctx;
}