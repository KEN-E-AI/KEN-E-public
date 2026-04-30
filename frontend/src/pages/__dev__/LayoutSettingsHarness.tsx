import { LayoutSettings } from "@/components/layout/LayoutSettings";
import type {
  SettingsNavRow,
  SettingsNavRowId,
} from "@/components/layout/LayoutSettings";

const FIXTURE_ROWS: SettingsNavRow[] = [
  {
    id: "organization" as SettingsNavRowId,
    label: "Organization",
    path: "/settings/organization",
    order: 10,
  },
  {
    id: "account" as SettingsNavRowId,
    label: "Account",
    path: "/settings/account",
    order: 20,
  },
  {
    id: "user" as SettingsNavRowId,
    label: "User",
    path: "/settings/user",
    order: 30,
  },
  {
    id: "hidden" as SettingsNavRowId,
    label: "Should Not Appear",
    path: "/settings/hidden",
    order: 99,
    isVisible: false,
  },
];

export function LayoutSettingsHarness() {
  return (
    <LayoutSettings subNavItems={FIXTURE_ROWS}>
      <div className="space-y-4">
        <p className="text-[var(--color-text-secondary)] text-sm">
          Dev harness — verify sub-nav, header, and responsive layout above.
        </p>
        <ul className="text-[var(--color-text-secondary)] text-sm space-y-1 list-disc list-inside">
          <li>
            Sub-nav shows 3 rows (Organization / Account / User) sorted by order
          </li>
          <li>
            &ldquo;Should Not Appear&rdquo; row (isVisible: false) must not
            render
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
