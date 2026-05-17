import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

type Props = { children: ReactNode };

export function SuperAdminGuard({ children }: Props) {
  const { isSuperAdmin, isSuperAdminLoading } = useAuth();
  if (isSuperAdminLoading) return null;
  if (!isSuperAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}
