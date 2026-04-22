import { useState, useRef, useEffect, useCallback } from 'react';
import { Bell, Check, Eye, Trash2, X } from 'lucide-react';
import { Notification } from '../data/mockData';
import { Button } from './ui/button';
import { cn } from './ui/utils';

interface NotificationBellProps {
  notifications: Notification[];
  onMarkAsRead?: (id: string) => void;
  onDelete?: (id: string) => void;
  onView?: (id: string) => void;
}

export function NotificationBell({ 
  notifications, 
  onMarkAsRead, 
  onDelete, 
  onView 
}: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; right: number }>({ top: 0, right: 0 });
  
  const unreadCount = notifications.filter(n => !n.isRead).length;

  const updatePosition = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 8,
        right: Math.max(8, window.innerWidth - rect.right),
      });
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, updatePosition]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        triggerRef.current && !triggerRef.current.contains(target) &&
        contentRef.current && !contentRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const timer = setTimeout(() => document.addEventListener('mousedown', handler), 0);
    return () => { clearTimeout(timer); document.removeEventListener('mousedown', handler); };
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const getNotificationIcon = (type: Notification['type']) => {
    switch (type) {
      case 'error':
        return '🔴';
      case 'warning':
        return '⚠️';
      case 'success':
        return '✅';
      default:
        return 'ℹ️';
    }
  };

  const formatTimestamp = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <Button
        ref={triggerRef}
        variant="ghost"
        size="icon"
        className="relative"
        onClick={() => setOpen(o => !o)}
      >
        <Bell className="size-5" />
        {unreadCount > 0 && (
          <span 
            className="absolute -top-1 -right-1 size-5 rounded-full bg-[#F97066] text-[var(--color-text-inverse)] text-[10px] font-bold flex items-center justify-center"
            style={{
              boxShadow: '0 0 6px rgba(249, 112, 102, 0.5)',
            }}
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div
          ref={contentRef}
          className="w-[28rem] max-w-[calc(100vw-16px)] bg-[var(--color-bg-elevated)] rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] shadow-lg p-0 flex flex-col"
          style={{
            position: 'fixed',
            top: position.top,
            right: position.right,
            zIndex: 9999,
            maxHeight: `calc(100vh - ${position.top + 16}px)`,
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {/* Header */}
          <div 
            className="p-4 flex items-center justify-between shrink-0"
            style={{
              borderBottom: '2px dashed var(--color-border-default)',
            }}
          >
            <div>
              <h3 
                className="text-[var(--text-heading-sm)] font-bold"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Notifications
              </h3>
              <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
                {unreadCount} unread
              </p>
            </div>
            <Button variant="ghost" size="icon" className="shrink-0" onClick={() => setOpen(false)}>
              <X className="size-4" />
            </Button>
          </div>

          {/* Notifications List */}
          <div className="overflow-y-auto flex-1 min-h-0 pr-1">
            {notifications.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-[var(--text-body-md)] text-[var(--color-text-tertiary)]">
                  No notifications
                </p>
              </div>
            ) : (
              <div className="p-2">
                {notifications.map(notification => (
                  <div
                    key={notification.id}
                    className={cn(
                      "p-3 rounded-[var(--radius-md)] mb-2 transition-all group",
                      notification.isRead 
                        ? "bg-[var(--color-bg-primary)] opacity-70" 
                        : "bg-[var(--color-bg-primary)] border-2 border-[var(--color-violet-300)]"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {/* Icon */}
                      <div className="text-xl shrink-0 mt-0.5">
                        {getNotificationIcon(notification.type)}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <p className="text-[var(--text-body-sm)] font-bold">
                            {notification.title}
                          </p>
                          {notification.actionRequired && (
                            <span className="shrink-0 px-2 py-0.5 rounded-[var(--radius-pill)] bg-[var(--color-red-500)] text-[var(--color-text-inverse)] text-[10px] font-bold uppercase">
                              Action
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[var(--color-text-secondary)] mb-1">
                          {notification.description}
                        </p>
                        <p className="text-[10px] text-[var(--color-text-tertiary)]">
                          {formatTimestamp(notification.timestamp)}
                        </p>

                        {/* Actions */}
                        <div className="flex items-center gap-2 mt-1 hidden group-hover:flex transition-opacity">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onView?.(notification.id)}
                            className="h-7 text-[var(--text-caption)]"
                          >
                            <Eye className="size-3 mr-1" />
                            View
                          </Button>
                          {!notification.isRead && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onMarkAsRead?.(notification.id)}
                              className="h-7 text-[var(--text-caption)]"
                            >
                              <Check className="size-3 mr-1" />
                              Mark read
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onDelete?.(notification.id)}
                            className="h-7 text-[var(--text-caption)] text-[var(--color-red-500)] hover:text-[var(--color-red-600)]"
                          >
                            <Trash2 className="size-3 mr-1" />
                            Delete
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div 
              className="p-3 shrink-0"
              style={{
                borderTop: '2px dashed var(--color-border-default)',
              }}
            >
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-[var(--text-body-sm)] text-[var(--color-violet-500)]"
                onClick={() => {
                  notifications.forEach(n => !n.isRead && onMarkAsRead?.(n.id));
                }}
              >
                Mark all as read
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}