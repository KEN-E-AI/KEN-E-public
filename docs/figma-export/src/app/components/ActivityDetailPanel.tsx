/**
 * ActivityDetailPanel — Read-only activity detail view with optional diff highlighting.
 *
 * Used by the Recommendations tab to preview add/modify/delete recommendations.
 * For modify recs, changed fields are shown with before → after treatment.
 */

import {
  X,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  DollarSign,
  Tag,
  User,
  Layers,
  Globe,
  Target,
  ArrowRight,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge } from './ui/badge';
import { cn } from './ui/utils';
import type { CalendarActivity } from '../data/calendarData';
import { getCampaignName, getPlatformColor, getUserName, getActivityObjective } from '../data/calendarData';
import type { RecommendationAction } from '../data/simulationRecommendations';

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatDate(d: Date): string {
  return `${MONTH_ABBR[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

function formatCurrency(v: number | null | undefined): string {
  if (v == null) return '—';
  return `$${v.toLocaleString()}`;
}

interface ActivityDetailPanelProps {
  activity: CalendarActivity;
  action?: RecommendationAction;
  /** For modify recs: the fields that changed (new values). */
  changes?: Partial<CalendarActivity>;
  /** For modify recs: the original values of changed fields. */
  originalValues?: Partial<CalendarActivity>;
  onClose: () => void;
}

export function ActivityDetailPanel({
  activity,
  action,
  changes,
  originalValues,
  onClose,
}: ActivityDetailPanelProps) {
  const platformColor = getPlatformColor(activity.platform);
  const campaignName = getCampaignName(activity.campaign_id);
  const ownerName = getUserName(activity.owner);

  // Merge activity with changes for display (modify recs show "after" state)
  const displayActivity = changes ? { ...activity, ...changes } : activity;

  // Which fields have changed?
  const changedFields = new Set(changes ? Object.keys(changes) : []);

  const bannerConfig = action
    ? {
        add: {
          bg: 'bg-emerald-50 border-emerald-200',
          text: 'text-emerald-800',
          icon: <Plus className="size-3.5" />,
          label: 'New Activity — AI recommends adding this to your calendar',
        },
        modify: {
          bg: 'bg-amber-50 border-amber-200',
          text: 'text-amber-800',
          icon: <Pencil className="size-3.5" />,
          label: 'Modification — AI recommends changing the highlighted fields',
        },
        delete: {
          bg: 'bg-red-50 border-red-200',
          text: 'text-red-800',
          icon: <Trash2 className="size-3.5" />,
          label: 'Removal — AI recommends removing this activity',
        },
      }[action]
    : null;

  return (
    <div className="w-96 shrink-0 border-l border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border-default)]">
        <h3 className="text-sm truncate pr-2">Activity Detail</h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground cursor-pointer">
          <X className="size-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Action banner */}
        {bannerConfig && (
          <div className={cn('flex items-start gap-2.5 px-4 py-3 border-b text-xs', bannerConfig.bg, bannerConfig.text)}>
            {bannerConfig.icon}
            <span>{bannerConfig.label}</span>
          </div>
        )}

        {/* Platform color bar */}
        <div className="h-1.5" style={{ backgroundColor: platformColor.color }} />

        <div className="px-4 py-4 space-y-4">
          {/* Name */}
          <div>
            <FieldLabel label="Activity Name" changed={changedFields.has('name')} />
            <DiffValue
              field="name"
              current={displayActivity.name}
              original={originalValues?.name}
              changed={changedFields.has('name')}
              render={(v) => <p className="text-sm">{v as string}</p>}
            />
          </div>

          {/* Objective */}
          <div>
            <FieldLabel label="Objective" changed={false} />
            <div className="flex items-center gap-2">
              <Target className="size-3.5 text-muted-foreground" />
              <span className="text-sm">{getActivityObjective(displayActivity) ?? '—'}</span>
            </div>
          </div>

          {/* Campaign */}
          <div>
            <FieldLabel label="Campaign" changed={changedFields.has('campaign_id')} />
            <DiffValue
              field="campaign_id"
              current={getCampaignName(displayActivity.campaign_id)}
              original={originalValues?.campaign_id ? getCampaignName(originalValues.campaign_id) : undefined}
              changed={changedFields.has('campaign_id')}
              render={(v) => (
                <div className="flex items-center gap-2">
                  <Layers className="size-3.5 text-muted-foreground" />
                  <span className="text-sm">{v as string}</span>
                </div>
              )}
            />
          </div>

          {/* Platform */}
          <div>
            <FieldLabel label="Platform" changed={changedFields.has('platform')} />
            <DiffValue
              field="platform"
              current={displayActivity.platform || '—'}
              original={originalValues?.platform}
              changed={changedFields.has('platform')}
              render={(v) => (
                <div className="flex items-center gap-2">
                  <Globe className="size-3.5 text-muted-foreground" />
                  <span className="text-sm">{v as string}</span>
                </div>
              )}
            />
          </div>

          {/* Cost */}
          <div>
            <FieldLabel label="Cost" changed={changedFields.has('cost')} />
            <DiffValue
              field="cost"
              current={formatCurrency(displayActivity.cost)}
              original={originalValues?.cost !== undefined ? formatCurrency(originalValues.cost as number | null) : undefined}
              changed={changedFields.has('cost')}
              render={(v) => (
                <div className="flex items-center gap-2">
                  <DollarSign className="size-3.5 text-muted-foreground" />
                  <span className="text-sm tabular-nums">{v as string}</span>
                </div>
              )}
            />
          </div>

          {/* Launch Date */}
          <div>
            <FieldLabel label="Launch Date" changed={changedFields.has('launch_date')} />
            <DiffValue
              field="launch_date"
              current={formatDate(displayActivity.launch_date)}
              original={originalValues?.launch_date ? formatDate(originalValues.launch_date as Date) : undefined}
              changed={changedFields.has('launch_date')}
              render={(v) => (
                <div className="flex items-center gap-2">
                  <Calendar className="size-3.5 text-muted-foreground" />
                  <span className="text-sm">{v as string}</span>
                </div>
              )}
            />
          </div>

          {/* Owner */}
          <div>
            <FieldLabel label="Owner" changed={changedFields.has('owner')} />
            <DiffValue
              field="owner"
              current={ownerName || '—'}
              original={originalValues?.owner ? getUserName(originalValues.owner) : undefined}
              changed={changedFields.has('owner')}
              render={(v) => (
                <div className="flex items-center gap-2">
                  <User className="size-3.5 text-muted-foreground" />
                  <span className="text-sm">{v as string}</span>
                </div>
              )}
            />
          </div>

          {/* Tags */}
          {displayActivity.tags.length > 0 && (
            <div>
              <FieldLabel label="Tags" changed={changedFields.has('tags')} />
              <div className="flex items-center gap-1 flex-wrap mt-1">
                <Tag className="size-3.5 text-muted-foreground" />
                {displayActivity.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-[0.625rem]">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Status */}
          <div>
            <FieldLabel label="Status" />
            <Badge variant="outline" className="text-[0.625rem]">
              {displayActivity.status}
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Helpers ─── */

function FieldLabel({ label, changed }: { label: string; changed?: boolean }) {
  return (
    <div className="flex items-center gap-1.5 mb-1">
      <span className="text-[0.625rem] text-muted-foreground tracking-wide uppercase">{label}</span>
      {changed && (
        <span className="text-[0.5625rem] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 tracking-wide uppercase">
          Changed
        </span>
      )}
    </div>
  );
}

/**
 * Renders a field value with optional before → after diff when changed.
 */
function DiffValue({
  current,
  original,
  changed,
  render,
}: {
  field: string;
  current: unknown;
  original?: unknown;
  changed: boolean;
  render: (v: unknown) => ReactNode;
}) {
  if (!changed || original === undefined) {
    return <>{render(current)}</>;
  }

  return (
    <div className="space-y-1">
      {/* Original (struck through) */}
      <div className="flex items-center gap-2 opacity-50">
        <div className="line-through">{render(original)}</div>
      </div>
      {/* Arrow + New */}
      <div className="flex items-center gap-2">
        <ArrowRight className="size-3 text-amber-500 shrink-0" />
        <div className="px-2 py-0.5 rounded bg-amber-50 border border-amber-200">
          {render(current)}
        </div>
      </div>
    </div>
  );
}