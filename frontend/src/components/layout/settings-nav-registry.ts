import type { Brand } from "@/lib/branded-types";

export type SettingsNavRowId = Brand<string, "SettingsNavRowId">;

export type SettingsNavRow = {
  id: SettingsNavRowId;
  label: string;
  path: string;
  order: number;
  isVisible?: () => boolean;
};

const _registry: SettingsNavRow[] = [];
export const SETTINGS_NAV_REGISTRY: ReadonlyArray<SettingsNavRow> = _registry;

const SAFE_PATH_RE = /^\/[a-zA-Z0-9/_-]+$/;
const SAFE_PATH_MAX_LEN = 200;

function isSafePath(path: string): boolean {
  if (
    path.length > SAFE_PATH_MAX_LEN ||
    path.includes("..") ||
    path.startsWith("/__")
  )
    return false;
  return SAFE_PATH_RE.test(path);
}

let _settingsNavVersion = 0;
const _settingsNavListeners = new Set<() => void>();

export function _settingsNavSubscribe(listener: () => void): () => void {
  _settingsNavListeners.add(listener);
  return () => {
    _settingsNavListeners.delete(listener);
  };
}

export function _getSettingsNavSnapshot(): number {
  return _settingsNavVersion;
}

export function registerSettingsNavRow(row: SettingsNavRow): void {
  if (!isSafePath(row.path)) {
    console.warn(
      `[registerSettingsNavRow] Rejected row "${row.id}": invalid path`,
    );
    return;
  }
  if (_registry.some((r) => r.id === row.id)) {
    console.warn(
      `[registerSettingsNavRow] Rejected row "${row.id}": duplicate id`,
    );
    return;
  }
  _registry.push(row);
  _settingsNavVersion += 1;
  _settingsNavListeners.forEach((listener) => listener());
}

export function resetSettingsNavForTesting(): void {
  if (import.meta.env.MODE !== "test") return;
  _registry.length = 0;
  _settingsNavVersion = 0;
  _settingsNavListeners.clear();
}

// Seed default rows at module import time
registerSettingsNavRow({
  id: "organization" as SettingsNavRowId,
  label: "Organization",
  path: "/settings/organization",
  order: 10,
});
registerSettingsNavRow({
  id: "account" as SettingsNavRowId,
  label: "Account",
  path: "/settings/account",
  order: 20,
});
registerSettingsNavRow({
  id: "user" as SettingsNavRowId,
  label: "User",
  path: "/settings/user",
  order: 30,
});
