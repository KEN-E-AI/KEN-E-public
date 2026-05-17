import { ShieldCheck } from "lucide-react";
import {
  registerSuperAdminNavRow,
  type NavRowId,
} from "@/components/layout/super-admin-nav-registry";

registerSuperAdminNavRow({
  id: "super-admins" as NavRowId,
  label: "Super Admins",
  path: "/admin/super-admins",
  order: 10,
  icon: ShieldCheck,
});
