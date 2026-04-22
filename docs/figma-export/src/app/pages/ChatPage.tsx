import { useState } from 'react';
import { ChatInterface } from '../components/ChatInterface';
import { SessionSettings } from '../components/SessionSettings';
import { Button } from '../components/ui/button';
import { ArrowLeftRight } from 'lucide-react';

export function ChatPage() {
  const [view, setView] = useState<'chat' | 'settings'>('chat');

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="mx-6 mt-6 mb-2">
        <Button
          variant="outline"
          onClick={() => setView(view === 'chat' ? 'settings' : 'chat')}
          className="gap-2 rounded-[var(--radius-pill)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-5 py-2.5 text-[var(--text-body-sm)] font-bold text-[var(--color-text-tertiary)] hover:border-[var(--color-teal-300)] hover:text-[var(--color-teal-500)] hover:-translate-y-0.5 transition-all"
          style={{
            transitionTimingFunction: 'var(--ease-bounce)',
            transitionDuration: 'var(--duration-default)',
          }}
        >
          <ArrowLeftRight className="size-4" />
          {view === 'chat' ? 'Session Status' : 'Chat'}
        </Button>
      </div>

      {view === 'chat' ? (
        <div className="flex-1 min-h-0 overflow-hidden px-6 flex flex-col">
          <ChatInterface />
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          <SessionSettings />
        </div>
      )}
    </div>
  );
}