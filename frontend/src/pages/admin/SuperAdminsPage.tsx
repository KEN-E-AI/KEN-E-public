import { useState } from "react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useSuperAdmins,
  useGrantSuperAdmin,
  useRevokeSuperAdmin,
} from "@/queries/superAdmins";
import type { GrantSuperAdminRequest } from "@/data/superAdminsApi";
import { SuperAdminsTable } from "@/components/admin/superAdmins/SuperAdminsTable";
import { GrantSuperAdminForm } from "@/components/admin/superAdmins/GrantSuperAdminForm";
import { RevokeConfirmDialog } from "@/components/admin/superAdmins/RevokeConfirmDialog";

type RevokeTarget = { uid: string; email: string | null };

export default function SuperAdminsPage() {
  const { data, isLoading } = useSuperAdmins();
  const grantMutation = useGrantSuperAdmin();
  const revokeMutation = useRevokeSuperAdmin();

  const [grantError, setGrantError] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<RevokeTarget | null>(null);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);

  const handleGrant = (body: GrantSuperAdminRequest) => {
    setGrantError(null);
    grantMutation.mutate(body, {
      onSuccess: (entry) => {
        toast.success(
          `Super-admin access granted to ${entry.email ?? entry.uid}`,
        );
      },
      onError: (err: unknown) => {
        const axiosErr = err as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        const detail =
          axiosErr.response?.data?.detail ??
          axiosErr.message ??
          "Unknown error";
        setGrantError(detail);
      },
    });
  };

  const handleRevokeClick = (uid: string) => {
    const entry = data?.super_admins.find((e) => e.uid === uid) ?? {
      uid,
      email: null,
    };
    setRevokeTarget({ uid: entry.uid, email: entry.email });
    setRevokeDialogOpen(true);
  };

  const handleRevokeConfirm = () => {
    if (!revokeTarget) return;
    revokeMutation.mutate(revokeTarget.uid, {
      onSuccess: () => {
        toast.success(
          `Super-admin access revoked from ${revokeTarget.email ?? revokeTarget.uid}`,
        );
        setRevokeDialogOpen(false);
        setRevokeTarget(null);
      },
      onError: (err: unknown) => {
        const axiosErr = err as {
          response?: { status?: number; data?: { detail?: string } };
          message?: string;
        };
        if (axiosErr.response?.status === 409) {
          toast.error("Cannot revoke the last remaining super admin");
        } else {
          const detail =
            axiosErr.response?.data?.detail ??
            axiosErr.message ??
            "Unknown error";
          toast.error(detail);
        }
        setRevokeDialogOpen(false);
        setRevokeTarget(null);
      },
    });
  };

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-[var(--text-heading-lg)] font-bold text-[var(--color-text-primary)]">
          Super Admins
        </h1>
        <p className="text-[var(--text-body-md)] text-[var(--color-text-secondary)] mt-1">
          Manage platform-staff access to KEN-E
        </p>
      </div>

      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card p-4 space-y-3">
        <h2 className="text-[var(--text-body-md)] font-bold text-[var(--color-text-primary)]">
          Grant access
        </h2>
        <GrantSuperAdminForm
          onGrant={handleGrant}
          isPending={grantMutation.isPending}
          error={grantError}
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <SuperAdminsTable
          entries={data?.super_admins ?? []}
          onRevoke={handleRevokeClick}
          isRevoking={revokeMutation.isPending}
          revokingUid={revokeTarget?.uid ?? null}
        />
      )}

      {revokeTarget && (
        <RevokeConfirmDialog
          open={revokeDialogOpen}
          onOpenChange={(open) => {
            setRevokeDialogOpen(open);
            if (!open) setRevokeTarget(null);
          }}
          targetEmail={revokeTarget.email}
          targetUid={revokeTarget.uid}
          onConfirm={handleRevokeConfirm}
          isPending={revokeMutation.isPending}
        />
      )}
    </div>
  );
}
