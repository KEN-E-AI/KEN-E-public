import { Flag } from "lucide-react";
import {
  registerSuperAdminNavRow,
  type NavRowId,
} from "@/components/layout/super-admin-nav-registry";

registerSuperAdminNavRow({
  id: "feature-flags" as NavRowId,
  label: "Feature Flags",
  path: "/admin/feature-flags",
  order: 20,
  icon: Flag,
});
