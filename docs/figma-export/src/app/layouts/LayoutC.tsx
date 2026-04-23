import { Outlet, Link, useLocation } from 'react-router';
import { 
  MessageSquare, 
  TrendingUp,
  Network,
  BookOpen,
  Puzzle,
  Settings,
  ChevronDown,
  Calendar
} from 'lucide-react';
import { useState, useRef } from 'react';
import { ChatInterface } from '../components/ChatInterface';
import { SessionsSidebar } from '../components/SessionsSidebar';
import { NotificationBell } from '../components/NotificationBell';
import { ProfileMenu } from '../components/ProfileMenu';
import { Logo } from '../components/Logo';
import { AccountSwitcher } from '../components/AccountSwitcher';
import { mockSessions, mockNotifications } from '../data/mockData';
import { cn } from '../components/ui/utils';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { ExtensionsProvider, useExtensions } from '../contexts/ExtensionsContext';

const navigation = [
  { name: 'Chat', href: '/', icon: MessageSquare },
  { name: 'Performance', href: '/performance', icon: TrendingUp },
  { name: 'Calendar', href: '/calendar', icon: Calendar },
  { name: 'Workflows', href: '/workflows', icon: Network },
  { name: 'Knowledge', href: '/strategy', icon: BookOpen },
  { name: 'Extensions', href: '/extensions', icon: Puzzle },
  { name: 'Settings', href: '/settings/account', icon: Settings },
];

export function LayoutC() {
  return (
    <ExtensionsProvider>
      <LayoutCInner />
    </ExtensionsProvider>
  );
}

const MINI_CHAT_DEFAULT_HEIGHT = 400;
const MINI_CHAT_MIN_HEIGHT = 200;

function LayoutCInner() {
  const location = useLocation();
  const [miniChatOpen, setMiniChatOpen] = useState(false);
  const [miniChatHeight, setMiniChatHeight] = useState(MINI_CHAT_DEFAULT_HEIGHT);
  const resizeStateRef = useRef<{ startY: number; startHeight: number } | null>(null);

  const handleResizePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    resizeStateRef.current = { startY: e.clientY, startHeight: miniChatHeight };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handleResizePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeStateRef.current) return;
    const delta = resizeStateRef.current.startY - e.clientY;
    const max = Math.max(MINI_CHAT_MIN_HEIGHT, window.innerHeight - 200);
    const next = Math.min(max, Math.max(MINI_CHAT_MIN_HEIGHT, resizeStateRef.current.startHeight + delta));
    setMiniChatHeight(next);
  };

  const handleResizePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeStateRef.current) return;
    resizeStateRef.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const isHome = location.pathname === '/';
  const isFullWidth = location.pathname.startsWith('/strategy') || location.pathname.startsWith('/workflows/automations') || location.pathname.startsWith('/performance/dashboards/');
  const currentPage = navigation.find(
    nav => nav.href === '/' 
      ? location.pathname === '/' 
      : location.pathname.startsWith(nav.href)
  );
  const activeSessions = mockSessions.filter(s => s.status !== 'complete').length;

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Top Navigation Bar - Desktop */}
      <div 
        className="bg-background hidden md:block relative"
        style={{
          borderBottom: '4px solid transparent',
          borderImage: 'var(--gradient-rainbow) 1',
        }}
      >
        <div className="flex items-center h-16 px-6">
          {/* Brand + Account Context zone */}
          <div className="flex items-center gap-2 shrink-0">
            <Logo variant="icon" size="sm" />
            <AccountSwitcher />
          </div>

          {/* Vertical separator between context and navigation */}
          <div className="h-8 w-px bg-[var(--color-border-default)] mx-5 shrink-0" />

          <nav className="flex items-center gap-1 lg:gap-2 flex-1">
            <TooltipProvider>
            {navigation.map((item) => {
              const isActive = item.href === '/' 
                ? location.pathname === '/'
                : location.pathname.startsWith(item.href);
              
              if (item.name === 'Extensions') {
                return <ExtensionsNavItem key={item.name} item={item} isActive={isActive} />;
              }

              return (
                <Tooltip key={item.name}>
                  <TooltipTrigger asChild>
                    <Link
                      to={item.href}
                      className={cn(
                        "flex items-center gap-2 p-2 lg:px-4 lg:py-2 rounded-[var(--radius-pill)] transition-all text-[var(--text-body-sm)] font-bold",
                        isActive
                          ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                          : "text-[var(--color-text-tertiary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5"
                      )}
                      style={{
                        transitionTimingFunction: 'var(--ease-bounce)',
                        transitionDuration: 'var(--duration-fast)',
                      }}
                    >
                      <item.icon className="size-4" />
                      <span className="hidden lg:inline">{item.name}</span>
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent className="lg:hidden">
                    {item.name}
                  </TooltipContent>
                </Tooltip>
              );
            })}
            </TooltipProvider>
          </nav>

          <div className="flex items-center gap-2">
            <NotificationBell 
              notifications={mockNotifications}
              onMarkAsRead={(id) => console.log('Mark as read:', id)}
              onDelete={(id) => console.log('Delete:', id)}
              onView={(id) => console.log('View:', id)}
            />
            <ProfileMenu />
          </div>
        </div>
      </div>

      {/* Mobile Header */}
      <div 
        className="bg-background px-4 py-3 flex items-center justify-between md:hidden relative"
        style={{
          borderBottom: '3px solid transparent',
          borderImage: 'var(--gradient-rainbow) 1',
        }}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="shrink-0">
            <Logo variant="icon" size="sm" />
          </div>
          <div className="min-w-0">
            <AccountSwitcher compact />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <NotificationBell 
            notifications={mockNotifications}
            onMarkAsRead={(id) => console.log('Mark as read:', id)}
            onDelete={(id) => console.log('Delete:', id)}
            onView={(id) => console.log('View:', id)}
          />
          <ProfileMenu />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Sessions Sidebar - Desktop only */}
        <div className="hidden md:flex md:flex-col md:min-h-0 md:h-full">
          <SessionsSidebar 
            sessions={mockSessions}
            onSessionSelect={(id) => console.log('Select session:', id)}
            onNewSession={() => console.log('New session')}
          />
        </div>
        
        {/* Page Content */}
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col bg-[var(--color-bg-secondary)]">
          <div
            className={`${isFullWidth ? '' : 'max-w-screen-2xl'} w-full flex-1 min-h-0 flex flex-col bg-[var(--color-bg-primary)]`}
            style={isFullWidth ? undefined : { borderRight: '2px dashed var(--color-border-default)' }}
          >
            <Outlet />
          </div>
        </div>
      </div>

      {/* Mini Chat Widget - Collapsible Bottom Bar (Desktop only, non-home pages) */}
      {!isHome && (
        <Collapsible open={miniChatOpen} onOpenChange={setMiniChatOpen} className="hidden md:block">
          <div
            className="bg-background relative"
            style={{
              borderTop: miniChatOpen ? '3px solid transparent' : '4px solid transparent',
              borderImage: 'var(--gradient-rainbow) 1',
            }}
          >
            {miniChatOpen && (
              <div
                role="separator"
                aria-orientation="horizontal"
                aria-label="Resize chat panel"
                onPointerDown={handleResizePointerDown}
                onPointerMove={handleResizePointerMove}
                onPointerUp={handleResizePointerUp}
                onPointerCancel={handleResizePointerUp}
                className="absolute left-0 right-0 -top-1.5 h-3 z-20 cursor-ns-resize"
                style={{ touchAction: 'none' }}
                title="Drag to resize"
              />
            )}
            <CollapsibleTrigger
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-[var(--color-accent)] transition-all rounded-none"
              style={{
                transitionTimingFunction: 'var(--ease-default)',
                transitionDuration: 'var(--duration-fast)',
              }}
            >
              <div className="flex items-center gap-3">
                <div 
                  className="size-10 rounded-[var(--radius-md)] bg-[var(--color-blue-500)] flex items-center justify-center -rotate-3"
                  style={{
                    boxShadow: 'var(--shadow-color-blue)',
                  }}
                >
                  <MessageSquare className="size-5 text-[var(--color-text-inverse)]" />
                </div>
                <div className="text-left">
                  <p className="text-[var(--text-body-md)] font-bold">KEN-E</p>
                </div>
              </div>
              <ChevronDown 
                className={cn(
                  "size-4 transition-transform text-[var(--color-text-tertiary)]",
                  miniChatOpen && "rotate-180"
                )} 
              />
            </CollapsibleTrigger>

            <CollapsibleContent>
              <div
                className="relative flex flex-col"
                style={{
                  height: miniChatHeight,
                  borderTop: '2px dashed var(--color-border-default)',
                }}
              >
                <ChatInterface compact />
              </div>
            </CollapsibleContent>
          </div>
        </Collapsible>
      )}

      {/* Bottom Navigation - Mobile */}
      <nav 
        className="bg-background md:hidden relative"
        style={{
          borderTop: '3px solid transparent',
          borderImage: 'var(--gradient-rainbow) 1',
        }}
      >
        <div className="grid grid-cols-7 h-16">
          {navigation.map((item) => {
            const isActive = item.href === '/' 
              ? location.pathname === '/'
              : location.pathname.startsWith(item.href);
            
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 transition-all",
                  isActive
                    ? "text-[var(--color-violet-500)] scale-110"
                    : "text-[var(--color-text-tertiary)]"
                )}
                style={{
                  transitionTimingFunction: 'var(--ease-bounce)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                <item.icon className="size-5" />
                <span className="text-[10px] font-bold">{item.name}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

function ExtensionsNavItem({ item, isActive }: { item: { name: string, href: string, icon: any }, isActive: boolean }) {
  const { getActiveExtensionDefinitions } = useExtensions();
  const [hovered, setHovered] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const activeExtensions = getActiveExtensionDefinitions();

  const handleEnter = () => {
    clearTimeout(timeoutRef.current);
    setHovered(true);
  };
  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setHovered(false), 150);
  };

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            to={item.href}
            className={cn(
              "flex items-center gap-2 p-2 lg:px-4 lg:py-2 rounded-[var(--radius-pill)] transition-all text-[var(--text-body-sm)] font-bold",
              isActive
                ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                : "text-[var(--color-text-tertiary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5"
            )}
            style={{
              transitionTimingFunction: 'var(--ease-bounce)',
              transitionDuration: 'var(--duration-fast)',
            }}
          >
            <item.icon className="size-4" />
            <span className="hidden lg:inline">{item.name}</span>
          </Link>
        </TooltipTrigger>
        <TooltipContent className="lg:hidden">
          {item.name}
        </TooltipContent>
      </Tooltip>

      {/* Hover sub-menu */}
      {hovered && (
        <div className="absolute top-full left-0 mt-1 min-w-[200px] bg-[var(--color-bg-elevated)] border-2 border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg py-1 z-50">
          {activeExtensions.map((p) => (
            <Link
              key={p.id}
              to={`/extensions/${p.slug}`}
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] transition-colors"
              onClick={() => setHovered(false)}
            >
              <div
                className={`size-6 rounded-[var(--radius-sm)] flex items-center justify-center ${p.rotation}`}
                style={{ backgroundColor: p.color }}
              >
                <p.icon className="size-3 text-[var(--color-text-inverse)]" />
              </div>
              <span>{p.name}</span>
            </Link>
          ))}
          {activeExtensions.length > 0 && (
            <div className="border-t border-[var(--color-border-default)] my-1" />
          )}
          <Link
            to="/extensions"
            className="flex items-center gap-2.5 px-3 py-2 text-xs text-muted-foreground hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] transition-colors"
            onClick={() => setHovered(false)}
          >
            Browse all extensions
          </Link>
        </div>
      )}
    </div>
  );
}