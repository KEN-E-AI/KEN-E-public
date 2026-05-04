import {
  LayoutSettings,
  registerSettingsNavRow,
} from "@/components/layout/LayoutSettings";
import type { SettingsNavRowId } from "@/components/layout/LayoutSettings";

const sId = (value: string) => value as SettingsNavRowId;

// Organization / Account / User rows are seeded by settings-nav-registry.ts at import time.
// Only register harness-specific extras here.
registerSettingsNavRow({
  id: sId("hidden"),
  label: "Should Not Appear",
  path: "/settings/hidden",
  order: 99,
  isVisible: () => false,
});

export function LayoutSettingsHarness() {
  return (
    <LayoutSettings>
      <div className="space-y-4">
        <p className="text-[var(--color-text-secondary)] text-sm">
          Dev harness — verify sub-nav, header, and responsive layout above.
        </p>
        <ul className="text-[var(--color-text-secondary)] text-sm space-y-1 list-disc list-inside">
          <li>
            Sub-nav shows 3 rows (Organization / Account / User) sorted by order
          </li>
          <li>
            &ldquo;Should Not Appear&rdquo; row (isVisible: () =&gt; false) must
            not render
          </li>
          <li>
            No row is highlighted (path /__dev__/layout-settings matches no row)
          </li>
          <li>
            Mobile (&lt;768px): aside collapses to horizontal scrollable strip
          </li>
          <li>Desktop (≥768px): aside shows as persistent left rail</li>
        </ul>
      </div>
    </LayoutSettings>
  );
}
