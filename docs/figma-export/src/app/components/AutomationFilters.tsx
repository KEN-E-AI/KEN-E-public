import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown, X, Search } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

// ─── Types ───

export interface AutomationFilterState {
  goal: string;
  campaignId: string;
  tags: string[];
  status: string;
  createdBy: string;
  isActive: string; // 'all' | 'active' | 'inactive'
}

export const defaultFilters: AutomationFilterState = {
  goal: '',
  campaignId: '',
  tags: [],
  status: '',
  createdBy: '',
  isActive: 'all',
};

export function hasActiveFilters(f: AutomationFilterState): boolean {
  return (
    f.goal !== '' ||
    f.campaignId !== '' ||
    f.tags.length > 0 ||
    f.status !== '' ||
    f.createdBy !== '' ||
    f.isActive !== 'all'
  );
}

// ─── Filter Options (derived from data) ───

interface FilterOptions {
  goals: string[];
  campaigns: { id: string; name: string }[];
  tags: string[];
  statuses: string[];
  creators: string[];
}

interface AutomationFiltersProps {
  filters: AutomationFilterState;
  onChange: (filters: AutomationFilterState) => void;
  options: FilterOptions;
  totalResults: number;
  totalItems: number;
}

export function AutomationFilters({
  filters,
  onChange,
  options,
  totalResults,
  totalItems,
}: AutomationFiltersProps) {
  const activeCount =
    (filters.goal ? 1 : 0) +
    (filters.campaignId ? 1 : 0) +
    (filters.tags.length > 0 ? 1 : 0) +
    (filters.status ? 1 : 0) +
    (filters.createdBy ? 1 : 0) +
    (filters.isActive !== 'all' ? 1 : 0);

  const set = (partial: Partial<AutomationFilterState>) =>
    onChange({ ...filters, ...partial });

  return (
    <div className="space-y-3">
      {/* Filter row */}
      <div className="flex items-center gap-2 flex-wrap">
        <Search className="size-4 text-muted-foreground shrink-0" />

        <SingleSelectFilter
          label="Goal"
          value={filters.goal}
          options={options.goals.map(g => ({ value: g, label: g }))}
          onChange={v => set({ goal: v })}
        />

        <SingleSelectFilter
          label="Campaign"
          value={filters.campaignId}
          options={options.campaigns.map(c => ({ value: c.id, label: c.name }))}
          onChange={v => set({ campaignId: v })}
        />

        <MultiSelectFilter
          label="Tags"
          values={filters.tags}
          options={options.tags}
          onChange={v => set({ tags: v })}
        />

        <SingleSelectFilter
          label="Status"
          value={filters.status}
          options={options.statuses.map(s => ({
            value: s,
            label: s.charAt(0).toUpperCase() + s.slice(1),
          }))}
          onChange={v => set({ status: v })}
        />

        <SingleSelectFilter
          label="Created By"
          value={filters.createdBy}
          options={options.creators.map(c => ({ value: c, label: c }))}
          onChange={v => set({ createdBy: v })}
        />

        <SingleSelectFilter
          label="Active"
          value={filters.isActive}
          options={[
            { value: 'all', label: 'All' },
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Inactive' },
          ]}
          onChange={v => set({ isActive: v })}
          allowEmpty={false}
        />

        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-muted-foreground"
            onClick={() => onChange(defaultFilters)}
          >
            <X className="size-3" />
            Clear ({activeCount})
          </Button>
        )}
      </div>

      {/* Results summary */}
      {activeCount > 0 && (
        <p className="text-xs text-muted-foreground">
          Showing {totalResults} of {totalItems} automations
        </p>
      )}
    </div>
  );
}

// ─── Single Select Dropdown ───

function SingleSelectFilter({
  label,
  value,
  options,
  onChange,
  allowEmpty = true,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  allowEmpty?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);
  useOutsideClick(ref, close, open);

  const selectedLabel = options.find(o => o.value === value)?.label;
  const isFiltered = allowEmpty ? !!value : value !== 'all';

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-[var(--radius-md)] border transition-colors ${
          isFiltered
            ? 'border-[var(--color-violet-500)] bg-[var(--color-violet-500)]/10 text-[var(--color-violet-500)]'
            : 'border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]'
        }`}
      >
        {label}
        {isFiltered && selectedLabel ? `: ${selectedLabel}` : ''}
        <ChevronDown className="size-3" />
      </button>

      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 min-w-[180px] max-h-[240px] overflow-auto rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] shadow-lg py-1">
          {allowEmpty && (
            <DropdownItem
              label={`All ${label}s`}
              selected={!value}
              onClick={() => {
                onChange('');
                setOpen(false);
              }}
            />
          )}
          {options.map(opt => (
            <DropdownItem
              key={opt.value}
              label={opt.label}
              selected={value === opt.value}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Multi Select Dropdown (Tags) ───

function MultiSelectFilter({
  label,
  values,
  options,
  onChange,
}: {
  label: string;
  values: string[];
  options: string[];
  onChange: (values: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);
  useOutsideClick(ref, close, open);

  const isFiltered = values.length > 0;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-[var(--radius-md)] border transition-colors ${
          isFiltered
            ? 'border-[var(--color-violet-500)] bg-[var(--color-violet-500)]/10 text-[var(--color-violet-500)]'
            : 'border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]'
        }`}
      >
        {label}
        {isFiltered && (
          <Badge variant="secondary" className="ml-0.5 px-1.5 py-0 text-[10px]">
            {values.length}
          </Badge>
        )}
        <ChevronDown className="size-3" />
      </button>

      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 min-w-[200px] max-h-[260px] overflow-auto rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] shadow-lg py-1">
          {values.length > 0 && (
            <button
              onClick={() => onChange([])}
              className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent transition-colors"
            >
              Clear selection
            </button>
          )}
          {options.map(tag => {
            const selected = values.includes(tag);
            return (
              <button
                key={tag}
                onClick={() => {
                  if (selected) {
                    onChange(values.filter(v => v !== tag));
                  } else {
                    onChange([...values, tag]);
                  }
                }}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-accent transition-colors flex items-center gap-2 ${
                  selected ? 'text-[var(--color-violet-500)]' : ''
                }`}
              >
                <span
                  className={`size-3.5 rounded border flex items-center justify-center shrink-0 ${
                    selected
                      ? 'bg-[var(--color-violet-500)] border-[var(--color-violet-500)]'
                      : 'border-[var(--color-border-default)]'
                  }`}
                >
                  {selected && (
                    <svg viewBox="0 0 12 12" className="size-2.5 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M2 6l3 3 5-5" />
                    </svg>
                  )}
                </span>
                {tag}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Shared ───

function DropdownItem({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-accent transition-colors ${
        selected ? 'text-[var(--color-violet-500)]' : ''
      }`}
    >
      {label}
    </button>
  );
}

function useOutsideClick(
  ref: React.RefObject<HTMLDivElement | null>,
  handler: () => void,
  enabled: boolean,
) {
  useEffect(() => {
    if (!enabled) return;
    function listener(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        handler();
      }
    }
    document.addEventListener('mousedown', listener);
    return () => document.removeEventListener('mousedown', listener);
  }, [ref, handler, enabled]);
}
