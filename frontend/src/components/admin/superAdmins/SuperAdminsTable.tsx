import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Props = {
  entries: Array<{ uid: string; email: string | null }>;
  onRevoke: (uid: string) => void;
  isRevoking: boolean;
  revokingUid: string | null;
};

export function SuperAdminsTable({
  entries,
  onRevoke,
  isRevoking,
  revokingUid,
}: Props) {
  if (entries.length === 0) {
    return (
      <div className="text-[var(--color-text-tertiary)] text-[var(--text-body-md)] py-6">
        No super admins yet.
      </div>
    );
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-card overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>UID</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => (
            <TableRow key={entry.uid}>
              <TableCell className="text-[var(--color-text-primary)]">
                {entry.email ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
                {entry.uid}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRevoke(entry.uid)}
                  disabled={isRevoking && revokingUid === entry.uid}
                  aria-label={`Revoke super-admin access for ${entry.email ?? entry.uid}`}
                >
                  {isRevoking && revokingUid === entry.uid
                    ? "Revoking…"
                    : "Revoke"}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
