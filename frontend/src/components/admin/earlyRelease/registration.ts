import { KeyRound } from "lucide-react";
import {
  registerSuperAdminNavRow,
  type NavRowId,
} from "@/components/layout/super-admin-nav-registry";

registerSuperAdminNavRow({
  id: "early-release" as NavRowId,
  label: "Early Release",
  path: "/admin/early-release",
  order: 30,
  icon: KeyRound,
});
