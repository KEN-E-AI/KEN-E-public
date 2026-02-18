import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { RecoverableSessionInfo } from "@/services/chatService";

interface SessionRecoveryDialogProps {
  open: boolean;
  sessions: RecoverableSessionInfo[];
  onRecover: (sessionId: string) => void;
  onDismiss: () => void;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);

  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function SessionRecoveryDialog({
  open,
  sessions,
  onRecover,
  onDismiss,
}: SessionRecoveryDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onDismiss()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Resume a previous conversation?</DialogTitle>
          <DialogDescription>
            You have recent conversations that can be restored.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-64 space-y-2 overflow-y-auto">
          {sessions.map((session) => (
            <button
              key={session.session_id}
              onClick={() => onRecover(session.session_id)}
              className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-accent"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">
                  {session.conversation_name || "Untitled Chat"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(session.last_updated)}
                </span>
              </div>
              {session.preview && (
                <p className="mt-1 truncate text-sm text-muted-foreground">
                  {session.preview}
                </p>
              )}
              {session.message_count > 0 && (
                <span className="mt-1 text-xs text-muted-foreground">
                  {session.message_count} messages
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="flex justify-end">
          <Button variant="ghost" onClick={onDismiss}>
            Start Fresh
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
