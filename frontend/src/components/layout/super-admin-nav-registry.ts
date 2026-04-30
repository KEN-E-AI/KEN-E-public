import type { Brand } from "@/lib/branded-types";

export type NavRowId = Brand<string, "NavRowId">;

export type SuperAdminNavRow = {
  id: NavRowId;
  label: string;
  path: string;
  order: number;
  icon?: React.ComponentType<{ className?: string }>;
  isVisible?: boolean;
};

export const SUPER_ADMIN_NAV: SuperAdminNavRow[] = [];

let _navVersion = 0;
const _navListeners = new Set<() => void>();

export function _navSubscribe(listener: () => void): () => void {
  _navListeners.add(listener);
  return () => {
    _navListeners.delete(listener);
  };
}

export function _getNavSnapshot(): number {
  return _navVersion;
}

export function registerSuperAdminNavRow(row: SuperAdminNavRow): void {
  if (!/^\/[a-zA-Z0-9/_-]*$/.test(row.path)) {
    console.warn(
      `[registerSuperAdminNavRow] Rejected row "${row.id}": invalid path`,
    );
    return;
  }
  if (SUPER_ADMIN_NAV.some((r) => r.id === row.id)) {
    console.warn(
      `[registerSuperAdminNavRow] Rejected row "${row.id}": duplicate id`,
    );
    return;
  }
  SUPER_ADMIN_NAV.push(row);
  _navVersion += 1;
  _navListeners.forEach((listener) => listener());
}

export function resetSuperAdminNavForTesting(): void {
  SUPER_ADMIN_NAV.length = 0;
  _navVersion = 0;
  _navListeners.clear();
}
