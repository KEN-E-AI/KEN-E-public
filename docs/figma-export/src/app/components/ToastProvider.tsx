/**
 * Lightweight toast system for Figma Make's sandboxed iframe.
 * Provides toast() function with optional undo action and auto-dismiss.
 */

import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';
import { X, Undo2 } from 'lucide-react';
import { cn } from './ui/utils';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'info' | 'error';
  action?: { label: string; onClick: () => void };
}

interface ToastContextValue {
  showToast: (
    message: string,
    opts?: {
      type?: 'success' | 'info' | 'error';
      duration?: number;
      action?: { label: string; onClick: () => void };
    },
  ) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let _toastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (
      message: string,
      opts?: {
        type?: 'success' | 'info' | 'error';
        duration?: number;
        action?: { label: string; onClick: () => void };
      },
    ) => {
      const id = ++_toastId;
      const toast: Toast = {
        id,
        message,
        type: opts?.type ?? 'info',
        action: opts?.action,
      };
      setToasts((prev) => [...prev, toast]);
      const duration = opts?.duration ?? 4000;
      const timer = setTimeout(() => dismiss(id), duration);
      timers.current.set(id, timer);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-auto">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={cn(
                'flex items-center gap-3 px-4 py-3 rounded-[var(--radius-md)] shadow-lg border text-sm min-w-[280px] max-w-[420px] animate-in slide-in-from-bottom-2 fade-in duration-200',
                t.type === 'success' && 'bg-emerald-50 border-emerald-200 text-emerald-800',
                t.type === 'error' && 'bg-red-50 border-red-200 text-red-800',
                t.type === 'info' && 'bg-[var(--color-bg-elevated)] border-[var(--color-border-default)] text-foreground',
              )}
            >
              <span className="flex-1 text-xs">{t.message}</span>
              {t.action && (
                <button
                  onClick={() => {
                    t.action!.onClick();
                    dismiss(t.id);
                  }}
                  className="flex items-center gap-1 text-xs text-[var(--color-violet-600)] hover:text-[var(--color-violet-800)] cursor-pointer whitespace-nowrap"
                >
                  <Undo2 className="size-3" />
                  {t.action.label}
                </button>
              )}
              <button
                onClick={() => dismiss(t.id)}
                className="text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
