import type {
  SettingsNavRow,
  SettingsNavRowId,
} from "@/components/layout/LayoutSettings";

export const SETTINGS_NAV_ITEMS: SettingsNavRow[] = [
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
];
