import { useSyncExternalStore } from "react";
import type { Brand } from "@/lib/branded-types";
import { Sidebar } from "./Sidebar";
import { TopNav } from "./TopNav";

export type LayoutBannerId = Brand<string, "LayoutBannerId">;

export type LayoutBannerRow = {
  id: LayoutBannerId;
  order: number;
  component: React.ComponentType;
  isVisible?: boolean;
};

const _LAYOUT_BANNER_REGISTRY: LayoutBannerRow[] = [];
export const LAYOUT_BANNER_REGISTRY: ReadonlyArray<LayoutBannerRow> =
  _LAYOUT_BANNER_REGISTRY;

let _bannerVersion = 0;
const _bannerListeners = new Set<() => void>();

function _bannerSubscribe(listener: () => void): () => void {
  _bannerListeners.add(listener);
  return () => {
    _bannerListeners.delete(listener);
  };
}

function _getBannerSnapshot(): number {
  return _bannerVersion;
}

export function registerLayoutBanner(row: LayoutBannerRow): void {
  if (_LAYOUT_BANNER_REGISTRY.some((r) => r.id === row.id)) {
    if (import.meta.env.DEV) {
      console.warn(
        `[registerLayoutBanner] Rejected row "${row.id}": duplicate id`,
      );
    }
    return;
  }
  _LAYOUT_BANNER_REGISTRY.push(row);
  _bannerVersion += 1;
  _bannerListeners.forEach((listener) => listener());
}

export function unregisterLayoutBanner(id: LayoutBannerId): void {
  const index = _LAYOUT_BANNER_REGISTRY.findIndex((r) => r.id === id);
  if (index !== -1) {
    _LAYOUT_BANNER_REGISTRY.splice(index, 1);
    _bannerVersion += 1;
    _bannerListeners.forEach((listener) => listener());
  }
}

export function resetLayoutBannersForTesting(): void {
  if (!import.meta.env.DEV) return;
  _LAYOUT_BANNER_REGISTRY.length = 0;
  _bannerVersion = 0;
  _bannerListeners.clear();
}

type LayoutCProps = {
  children: React.ReactNode;
};

export function LayoutC({ children }: LayoutCProps) {
  useSyncExternalStore(
    _bannerSubscribe,
    _getBannerSnapshot,
    _getBannerSnapshot,
  );

  const visibleBanners = LAYOUT_BANNER_REGISTRY.filter(
    (row) => row.isVisible !== false,
  ).sort((a, b) => a.order - b.order);

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <header className="shrink-0">
          <TopNav />
        </header>
        {visibleBanners.length > 0 && (
          <div role="region" aria-label="System banners" className="shrink-0">
            {visibleBanners.map((row) => {
              const BannerComponent = row.component;
              return <BannerComponent key={row.id} />;
            })}
          </div>
        )}
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
