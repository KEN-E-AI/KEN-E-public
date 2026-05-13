import { MessageSquare } from 'lucide-react';
import { Button } from './ui/button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[25rem] p-8 text-center">
      <div className="rounded-full bg-muted p-6 mb-4">
        {icon || <MessageSquare className="size-8 text-muted-foreground" />}
      </div>
      <h3 className="mb-2">{title}</h3>
      <p className="text-muted-foreground mb-6 max-w-md">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button onClick={onAction}>
          <MessageSquare className="size-4 mr-2" />
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
