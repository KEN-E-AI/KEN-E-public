import { useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { cn } from './ui/utils';

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const MONTH_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

interface MonthYearPickerProps {
  month: number;
  year: number;
  onSelect: (month: number, year: number) => void;
  minYear?: number;
  maxYear?: number;
}

export function MonthYearPicker({ month, year, onSelect, minYear = 2024, maxYear = 2026 }: MonthYearPickerProps) {
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(year);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setViewYear(year);
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, year]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] text-sm cursor-pointer transition-colors hover:border-[var(--color-border-strong)]",
          open && "border-[var(--color-violet-500)] ring-1 ring-[var(--color-violet-500)]/20"
        )}
      >
        <Calendar className="size-3.5 text-muted-foreground" />
        <span>{MONTH_FULL[month]} {year}</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1.5 z-50 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg p-3 w-[16.25rem]">
          {/* Year navigation */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setViewYear(v => Math.max(minYear, v - 1))}
              disabled={viewYear <= minYear}
              className="size-7 flex items-center justify-center rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="text-sm" style={{ fontFamily: 'var(--font-display)' }}>{viewYear}</span>
            <button
              onClick={() => setViewYear(v => Math.min(maxYear, v + 1))}
              disabled={viewYear >= maxYear}
              className="size-7 flex items-center justify-center rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>

          {/* Month grid */}
          <div className="grid grid-cols-3 gap-1.5">
            {MONTHS.map((m, i) => {
              const isSelected = i === month && viewYear === year;
              return (
                <button
                  key={i}
                  onClick={() => {
                    onSelect(i, viewYear);
                    setOpen(false);
                  }}
                  className={cn(
                    "px-2 py-2 rounded-[var(--radius-sm)] text-sm cursor-pointer transition-all",
                    isSelected
                      ? "bg-[var(--color-violet-500)] text-white shadow-sm"
                      : "hover:bg-[var(--color-bg-secondary)] text-muted-foreground hover:text-foreground"
                  )}
                  style={{
                    transitionTimingFunction: 'var(--ease-default)',
                    transitionDuration: 'var(--duration-fast)',
                  }}
                >
                  {m}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
