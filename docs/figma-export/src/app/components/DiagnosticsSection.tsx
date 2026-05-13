import { useState } from 'react';
import {
  Stethoscope,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Loader2,
  Check,
  XCircle,
  Clock,
} from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';
import { cn } from './ui/utils';
import {
  MOCK_DIAGNOSTICS,
  type HealthStatus,
  type HealthIssue,
  type StatCard,
  type AdfRow,
  type ResidualRow,
} from '../data/diagnosticsData';

/* ========== Health badge config ========== */

const HEALTH_CONFIG: Record<HealthStatus, { label: string; dot: string; bg: string; text: string; border: string }> = {
  green: { label: 'Healthy', dot: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  yellow: { label: 'Attention Needed', dot: 'bg-amber-500', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  red: { label: 'Action Required', dot: 'bg-red-500', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

/* ========== Re-estimate button states ========== */

type ReEstimateState = 'idle' | 'loading' | 'success' | 'error' | 'timeout';

/* ========== DiagnosticsSection ========== */

export function DiagnosticsSection() {
  const data = MOCK_DIAGNOSTICS;
  const [reEstState, setReEstState] = useState<ReEstimateState>('idle');

  const handleReEstimate = async () => {
    setReEstState('loading');
    // Simulate async re-estimation (2s)
    await new Promise((r) => setTimeout(r, 2000));
    setReEstState('success');
    setTimeout(() => setReEstState('idle'), 5000);
  };

  const healthCfg = HEALTH_CONFIG[data.healthStatus];
  const hasIssues = data.healthStatus !== 'green' && data.issues.length > 0;

  return (
    <div className="space-y-5">
      {/* ===== 1. Page Header ===== */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Stethoscope className="size-5 text-[var(--color-violet-500)]" />
          <div>
            <div className="flex items-center gap-2.5">
              <h2>Diagnostics</h2>
              {/* Health badge */}
              {hasIssues ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[0.6875rem] border cursor-default',
                        healthCfg.bg, healthCfg.text, healthCfg.border,
                      )}
                    >
                      <span className={cn('size-1.5 rounded-full', healthCfg.dot)} />
                      {healthCfg.label}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-xs text-left">
                    <ul className="list-disc pl-3.5 space-y-1">
                      {data.issues.map((issue) => (
                        <li key={issue.id} className="text-[0.6875rem]">{issue.summary}</li>
                      ))}
                    </ul>
                  </TooltipContent>
                </Tooltip>
              ) : (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[0.6875rem] border',
                    healthCfg.bg, healthCfg.text, healthCfg.border,
                  )}
                >
                  <span className={cn('size-1.5 rounded-full', healthCfg.dot)} />
                  {healthCfg.label}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Model diagnostics — lag order, information criteria, stationarity tests, and residual checks.
            </p>
          </div>
        </div>

        {/* Re-estimate button */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReEstimate}
            disabled={reEstState === 'loading'}
          >
            {reEstState === 'loading' ? (
              <>
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
                Estimating…
              </>
            ) : (
              <>
                <RefreshCw className="size-3.5 mr-1.5" />
                Re-estimate Model
              </>
            )}
          </Button>
          {reEstState === 'success' && (
            <span className="flex items-center gap-1.5 text-[0.6875rem] text-emerald-600">
              <Check className="size-3" />
              Model re-estimated successfully.
            </span>
          )}
          {reEstState === 'error' && (
            <span className="flex items-center gap-1.5 text-[0.6875rem] text-red-500">
              <XCircle className="size-3" />
              Model re-estimation failed. Please try again.
            </span>
          )}
          {reEstState === 'timeout' && (
            <span className="flex items-center gap-1.5 text-[0.6875rem] text-amber-600">
              <Clock className="size-3" />
              The request timed out. The model may still be running — check back shortly.
            </span>
          )}
        </div>
      </div>

      {/* ===== 2. Health Issues Alert ===== */}
      {hasIssues && <HealthIssuesAlert status={data.healthStatus} issues={data.issues} />}

      {/* ===== 3. Model Overview ===== */}
      <div>
        <h3 className="text-sm mb-3">Model Overview</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {data.statCards.map((card) => (
            <OverviewStatCard key={card.id} card={card} />
          ))}
        </div>
      </div>

      {/* ===== 4. Structural Break Alert ===== */}
      {data.structuralBreakDetected && (
        <div className="flex items-start gap-3 p-4 rounded-[var(--radius-md)] bg-red-50 border border-red-200">
          <AlertCircle className="size-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-red-800">Structural Break Detected</p>
            <p className="text-xs text-red-600 mt-1">
              A structural break has been detected in the data. Model estimates may be less reliable.
              Human review is recommended before relying on forecasts.
            </p>
          </div>
        </div>
      )}

      {/* ===== 5. ADF Stationarity Tests ===== */}
      <AdfSection rows={data.adfTests} />

      {/* ===== 6. Residual Diagnostics ===== */}
      <ResidualSection rows={data.residualDiagnostics} />
    </div>
  );
}

/* ========== Health Issues Alert ========== */

function HealthIssuesAlert({ status, issues }: { status: HealthStatus; issues: HealthIssue[] }) {
  const isRed = status === 'red';
  return (
    <div
      className={cn(
        'rounded-[var(--radius-md)] border p-4 space-y-3',
        isRed ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200',
      )}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className={cn('size-4', isRed ? 'text-red-500' : 'text-amber-500')} />
        <h3 className={cn('text-sm', isRed ? 'text-red-800' : 'text-amber-800')}>
          {isRed ? 'Model Health Issues' : 'Model Health Warnings'}
        </h3>
      </div>
      <div className="space-y-2">
        {issues.map((issue) => (
          <IssueCard key={issue.id} issue={issue} />
        ))}
      </div>
    </div>
  );
}

function IssueCard({ issue }: { issue: HealthIssue }) {
  const [expanded, setExpanded] = useState(issue.defaultExpanded ?? false);
  const isError = issue.severity === 'error';
  const Icon = isError ? AlertCircle : AlertTriangle;

  return (
    <div className="bg-white/70 rounded-[var(--radius-sm)] border border-black/5 p-3 space-y-2">
      {/* Summary */}
      <div className="flex items-start gap-2">
        <Icon className={cn('size-3.5 shrink-0 mt-0.5', isError ? 'text-red-500' : 'text-amber-500')} />
        <p className="text-xs">{issue.summary}</p>
      </div>
      {/* Action */}
      <p className="text-xs text-muted-foreground ml-5.5 pl-[22px]">
        <span className="text-foreground">Recommended action:</span> {issue.action}
      </p>
      {/* Technical details toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 ml-[22px] text-[0.6875rem] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        Technical details
      </button>
      {expanded && (
        <div className="ml-[22px] px-3 py-2 bg-[var(--color-bg-secondary)] rounded-[var(--radius-xs)] border border-[var(--color-border-default)]">
          <p className="text-[0.6875rem] text-muted-foreground font-mono leading-relaxed">{issue.technicalDetail}</p>
        </div>
      )}
    </div>
  );
}

/* ========== Overview Stat Card ========== */

function OverviewStatCard({ card }: { card: StatCard }) {
  const inner = (
    <Card
      className="p-3 relative overflow-hidden"
      style={{ borderLeft: `3px solid ${card.accentColor}` }}
    >
      <div className="flex items-center gap-1 mb-1.5">
        <span className="text-[0.6875rem] text-muted-foreground">{card.label}</span>
        {card.tooltip && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="size-3 text-muted-foreground/60 cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[13.75rem]">
              {card.tooltip}
            </TooltipContent>
          </Tooltip>
        )}
        {card.annotation && (
          <span className="text-[0.625rem] text-[var(--color-violet-500)]">{card.annotation}</span>
        )}
      </div>
      <p className="text-lg tabular-nums" style={{ fontFamily: 'var(--font-display)' }}>
        {card.value}
      </p>
    </Card>
  );

  return inner;
}

/* ========== Info Header Icon ========== */

function InfoHeaderIcon({ tooltip }: { tooltip: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info className="size-3 text-muted-foreground/60 cursor-help inline-block ml-1" />
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[13.75rem]">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

/* ========== Status Badge ========== */

function StatusBadge({ value, goodValue }: { value: string; goodValue: string }) {
  const isGood = value === goodValue;
  return (
    <Badge variant={isGood ? 'success' : 'error'} className="text-[0.625rem] px-2 py-0">
      {value}
    </Badge>
  );
}

/* ========== ADF Section ========== */

function AdfSection({ rows }: { rows: AdfRow[] }) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="text-sm">ADF Stationarity Tests</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          These checks verify that each funnel metric follows a stable, predictable pattern over time.
          A stable pattern means the model can learn from it and produce reliable forecasts.
        </p>
      </div>
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">Funnel Stage</th>
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">
                p-value
                <InfoHeaderIcon tooltip="A statistical confidence measure. Values below 0.05 indicate a stable pattern." />
              </th>
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">
                Status
                <InfoHeaderIcon tooltip="'Stable' means the metric has a reliable pattern the model can learn from. 'Unstable' means the pattern is drifting." />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.stage}
                className="border-b border-[var(--color-border-default)] last:border-b-0 hover:bg-[var(--color-bg-secondary)] transition-colors"
              >
                <td className="px-4 py-3 text-sm">{row.stage}</td>
                <td className="px-4 py-3 text-sm tabular-nums">{row.pValue.toFixed(4)}</td>
                <td className="px-4 py-3">
                  <StatusBadge value={row.status} goodValue="Stable" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

/* ========== Residual Diagnostics Section ========== */

function ResidualSection({ rows }: { rows: ResidualRow[] }) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="text-sm">Residual Diagnostics</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          These checks verify that the model's prediction errors are random.
          Patterns in the errors suggest the model may be missing something important.
        </p>
      </div>
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">Funnel Stage</th>
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">
                Autocorrelation
                <InfoHeaderIcon tooltip="Checks whether prediction errors follow a pattern. 'No issues' is the ideal result." />
              </th>
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">
                Durbin-Watson
                <InfoHeaderIcon tooltip="Measures error patterns. Values near 2.0 are ideal. Below 1.5 or above 2.5 indicates a problem." />
              </th>
              <th className="text-left px-4 py-3 text-xs text-muted-foreground tracking-wide">
                Normality
                <InfoHeaderIcon tooltip="Checks if errors follow a bell-curve distribution. 'Normal' means forecast confidence ranges are reliable." />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.stage}
                className="border-b border-[var(--color-border-default)] last:border-b-0 hover:bg-[var(--color-bg-secondary)] transition-colors"
              >
                <td className="px-4 py-3 text-sm">{row.stage}</td>
                <td className="px-4 py-3">
                  <StatusBadge value={row.autocorrelation} goodValue="No issues" />
                </td>
                <td className="px-4 py-3 text-sm tabular-nums">{row.durbinWatson.toFixed(4)}</td>
                <td className="px-4 py-3">
                  <StatusBadge value={row.normality} goodValue="Normal" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
