import { useState, useMemo } from 'react';
import { Search, Plus, ChevronLeft, Filter } from 'lucide-react';
import { AISession, sessionCategories } from '../data/mockData';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { cn } from './ui/utils';

interface SessionsSidebarProps {
  sessions: AISession[];
  onSessionSelect?: (sessionId: string) => void;
  onNewSession?: () => void;
}

export function SessionsSidebar({ sessions, onSessionSelect, onNewSession }: SessionsSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  const filteredSessions = useMemo(() => {
    return sessions.filter(session => {
      const matchesSearch = session.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = selectedCategory === 'All' || session.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [sessions, searchQuery, selectedCategory]);

  const activeSessionsCount = sessions.filter(s => s.isActive).length;
  const unreviewedCount = sessions.filter(s => s.hasUnreviewedTasks).length;

  if (isCollapsed) {
    return (
      <div 
        className="w-16 bg-[var(--color-bg-elevated)] flex flex-col items-center py-4 gap-4 h-full min-h-0"
        style={{
          borderRight: '2px dashed var(--color-border-default)',
        }}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsCollapsed(false)}
          className="shrink-0"
        >
          <ChevronLeft className="size-4 rotate-180" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onNewSession}
          className="shrink-0"
        >
          <Plus className="size-4" />
        </Button>
        <div className="flex flex-col gap-2 mt-4">
          {sessions.slice(0, 10).filter(session => session.isActive || session.hasUnreviewedTasks).map(session => {
            return (
              <button
                key={session.id}
                onClick={() => onSessionSelect?.(session.id)}
                className={cn(
                  "size-2.5 rounded-full transition-all hover:scale-125",
                  session.isActive
                    ? "bg-[var(--color-teal-500)]"
                    : "bg-[#F97066]"
                )}
                style={{
                  boxShadow: session.isActive
                    ? '0 0 4px rgba(16, 185, 129, 0.5)'
                    : '0 0 4px rgba(249, 112, 102, 0.5)',
                }}
                title={`${session.name}${session.isActive ? ' (Active)' : ' (Needs review)'}`}
              />
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div 
      className="w-96 bg-[var(--color-bg-elevated)] flex flex-col overflow-x-hidden"
      style={{
        borderRight: '2px dashed var(--color-border-default)',
      }}
    >
      {/* Header */}
      <div className="p-4 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 
              className="text-[var(--text-heading-sm)] font-bold"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Sessions
            </h2>
            <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
              {activeSessionsCount} active • {unreviewedCount} need review
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(true)}
            className="shrink-0"
          >
            <ChevronLeft className="size-4" />
          </Button>
        </div>

        {/* New Session Button */}
        <Button
          onClick={onNewSession}
          className="w-full mb-4"
          size="sm"
        >
          <Plus className="size-4 mr-2" />
          New Session
        </Button>

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-tertiary)]" />
          <Input
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Category Filter */}
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-tertiary)]" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)] text-[var(--text-body-sm)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-500)]"
          >
            <option value="All">All Categories</option>
            {sessionCategories.map(category => (
              <option key={category} value={category}>{category}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Sessions List */}
      <ScrollArea className="flex-1">
        <div className="px-4 pb-4 space-y-2">
          {filteredSessions.length === 0 ? (
            <p className="text-[var(--text-body-sm)] text-[var(--color-text-tertiary)] text-center py-8">
              No sessions found
            </p>
          ) : (
            filteredSessions.map(session => (
              <button
                key={session.id}
                onClick={() => onSessionSelect?.(session.id)}
                className={cn(
                  "w-full text-left p-2 rounded-[var(--radius-md)] border-2 transition-all group block",
                  "hover:bg-[var(--color-accent)] hover:border-[var(--color-violet-300)]",
                  "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
                )}
                style={{
                  transitionTimingFunction: 'var(--ease-default)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                <div className="flex items-start gap-2 min-w-0">
                  {/* Status Indicator */}
                  <div className="shrink-0 mt-1">
                    {session.isActive ? (
                      <div 
                        className="size-2.5 rounded-full bg-[var(--color-teal-500)]"
                        style={{
                          boxShadow: '0 0 4px rgba(16, 185, 129, 0.5)',
                        }}
                        title="Active session"
                      />
                    ) : session.hasUnreviewedTasks ? (
                      <div 
                        className="size-2.5 rounded-full bg-[#F97066]"
                        style={{
                          boxShadow: '0 0 4px rgba(249, 112, 102, 0.5)',
                        }}
                        title="Has unreviewed tasks"
                      />
                    ) : (
                      <div className="size-2.5" />
                    )}
                  </div>

                  {/* Session Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--text-body-sm)] font-medium truncate">
                      {session.name}
                    </p>
                    {session.category && (
                      <p className="text-[11px] text-[var(--color-text-tertiary)] truncate">
                        {session.category}
                      </p>
                    )}
                    {session.lastMessage && (
                      <p className="text-[10px] text-[var(--color-text-tertiary)] truncate mt-0.5">
                        {session.lastMessage}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}