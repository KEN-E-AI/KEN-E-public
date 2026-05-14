import { AISession } from '../data/mockData';
import { Badge } from './ui/badge';

interface SessionIndicatorProps {
  sessions: AISession[];
  compact?: boolean;
  onClick?: (sessionId: string) => void;
}

export function SessionIndicator({ sessions, compact = false, onClick }: SessionIndicatorProps) {
  const activeSessionsCount = sessions.filter(s => s.status !== 'complete').length;

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {sessions.slice(0, 3).map(session => (
          <button
            key={session.id}
            onClick={() => onClick?.(session.id)}
            className="size-2.5 rounded-full transition-all hover:scale-125"
            style={{ 
              backgroundColor: session.color,
              boxShadow: '0 0 4px rgba(0, 0, 0, 0.15)',
            }}
            title={session.name}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {sessions.map(session => (
        <button
          key={session.id}
          onClick={() => onClick?.(session.id)}
          className="group flex items-center gap-2 rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-2 transition-all hover:bg-[var(--color-accent)] hover:border-[var(--color-violet-300)]"
          style={{
            transitionTimingFunction: 'var(--ease-default)',
            transitionDuration: 'var(--duration-fast)',
          }}
        >
          <div
            className="size-2.5 rounded-full"
            style={{ 
              backgroundColor: session.color,
              boxShadow: '0 0 4px rgba(0, 0, 0, 0.15)',
            }}
          />
          <div className="flex flex-col items-start">
            <span className="text-[var(--text-body-sm)] font-medium">{session.name}</span>
            {session.lastMessage && (
              <span className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] max-w-[12.5rem] truncate">
                {session.lastMessage}
              </span>
            )}
          </div>
          <Badge variant={
            session.status === 'working' ? 'info' :
            session.status === 'complete' ? 'success' : 'neutral'
          }>
            {session.status}
          </Badge>
        </button>
      ))}
    </div>
  );
}