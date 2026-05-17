import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetEmail: string | null;
  targetUid: string;
  onConfirm: () => void;
  isPending: boolean;
};

export function RevokeConfirmDialog({
  open,
  onOpenChange,
  targetEmail,
  targetUid,
  onConfirm,
  isPending,
}: Props) {
  const displayTarget = targetEmail ?? targetUid;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revoke super-admin access</AlertDialogTitle>
          <AlertDialogDescription>
            This will remove super-admin privileges from{" "}
            <span className="font-medium text-[var(--color-text-primary)]">
              {displayTarget}
            </span>
            . This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className={cn(buttonVariants({ variant: "destructive" }))}
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Revoking…" : "Revoke"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
