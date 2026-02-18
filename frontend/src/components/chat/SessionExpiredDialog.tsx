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

interface SessionExpiredDialogProps {
  open: boolean;
  onRecover: () => void;
  onStartNew: () => void;
}

export function SessionExpiredDialog({
  open,
  onRecover,
  onStartNew,
}: SessionExpiredDialogProps) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Session Expired</AlertDialogTitle>
          <AlertDialogDescription>
            Your session has expired due to inactivity. Your data is preserved
            for up to 7 days and can be recovered.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onStartNew}>
            Start New Chat
          </AlertDialogCancel>
          <AlertDialogAction onClick={onRecover}>
            Recover Session
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
