import { Link } from 'react-router';
import { Puzzle } from 'lucide-react';
import { Badge } from './ui/badge';
import { getExtensionById, type ExtensionDefinition } from '../data/extensionRegistry';

interface OriginBadgeProps {
  extensionId?: string;
}

export function OriginBadge({ extensionId }: OriginBadgeProps) {
  if (!extensionId) return null;

  const extension: ExtensionDefinition | undefined = getExtensionById(extensionId);
  if (!extension) return null;

  return (
    <Link
      to={`/extensions/${extension.slug}`}
      onClick={(e) => e.stopPropagation()}
      className="inline-flex"
    >
      <Badge
        variant="outline"
        className="gap-1 text-[0.625rem] px-1.5 py-0.5 cursor-pointer hover:bg-[var(--color-bg-secondary)] transition-colors"
        style={{
          borderColor: extension.color,
          color: extension.color,
        }}
      >
        <Puzzle className="size-2.5" />
        {extension.name}
      </Badge>
    </Link>
  );
}
