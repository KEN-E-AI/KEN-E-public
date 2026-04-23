import { useEffect, useMemo, useRef, useState } from 'react';
import { Sparkles, AlertTriangle, MessageSquare } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { ArtifactRenderer } from './dashboard/ArtifactRenderer';
import { MonthYearPicker } from './MonthYearPicker';
import { mockAccounts, mockAccountUsers } from '../data/mockData';

const FREE_TOKEN_LIMIT = 500_000;

interface PricingStop {
  price: number;
  tokens: number;
}

// Tiered pricing: increment size grows as the allowance grows so the slider
// has a manageable number of stops. Each entry below describes a band, and
// PRICING_STOPS is built by stepping through each band.
//   Band 1: +500K tokens for +$30, up to $149 / 3M
//   Band 2: +1M tokens for +$60, up to $509 / 9M
//   Band 3: +1.5M tokens for +$90, up to $1,049 / 18M
//   Band 4: +2M tokens for +$120, up to $2,129 / 36M
//   Band 5: +3M tokens for +$180, up to $4,829 / 81M
const PRICING_BANDS: Array<{ priceStep: number; tokenStep: number; endPrice: number }> = [
  { priceStep: 30, tokenStep: 500_000, endPrice: 149 },
  { priceStep: 60, tokenStep: 1_000_000, endPrice: 509 },
  { priceStep: 90, tokenStep: 1_500_000, endPrice: 1_049 },
  { priceStep: 120, tokenStep: 2_000_000, endPrice: 2_129 },
  { priceStep: 180, tokenStep: 3_000_000, endPrice: 4_829 },
];

const PRICING_STOPS: PricingStop[] = (() => {
  const stops: PricingStop[] = [{ price: 29, tokens: 1_000_000 }];
  for (const band of PRICING_BANDS) {
    let current = stops[stops.length - 1];
    while (current.price < band.endPrice) {
      current = { price: current.price + band.priceStep, tokens: current.tokens + band.tokenStep };
      stops.push(current);
    }
  }
  return stops;
})();

const MAX_STOP_INDEX = PRICING_STOPS.length - 1;

type Breakdown = 'none' | 'account' | 'user';

interface DailyUsageRow {
  date: string;
  account: string;
  user: string;
  tokens: number;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${Number.isInteger(m) ? m.toFixed(0) : m.toFixed(1)}M`;
  }
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

function formatResetDate(): string {
  const now = new Date();
  const next = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return next.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Deterministic noise so the same (year, month) renders the same chart.
function noise(seed: number): number {
  const x = Math.sin(seed) * 10_000;
  return x - Math.floor(x);
}

function generateDailyUsage(
  year: number,
  month: number,
  accounts: typeof mockAccounts,
  users: typeof mockAccountUsers
): DailyUsageRow[] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month;
  const lastDay = isCurrentMonth ? today.getDate() : daysInMonth;

  // Round-robin assign each user to one account so breakdown=account aggregates cleanly.
  const userAccount = users.map((u, i) => ({ user: u, account: accounts[i % accounts.length] }));

  const rows: DailyUsageRow[] = [];
  for (let day = 1; day <= lastDay; day++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dow = new Date(year, month, day).getDay();
    const weekendFactor = dow === 0 || dow === 6 ? 0.4 : 1;
    userAccount.forEach(({ user, account }, ui) => {
      const seed = year * 1_000 + (month + 1) * 100 + day * 10 + ui;
      const tokens = Math.round(2_000 + noise(seed) * 12_000 * weekendFactor);
      rows.push({ date: dateStr, account: account.name, user: user.name, tokens });
    });
  }
  return rows;
}

function buildUsageSpec(rows: DailyUsageRow[], breakdown: Breakdown): Record<string, unknown> {
  const colorEncoding =
    breakdown === 'none'
      ? {}
      : {
          color: {
            field: breakdown,
            type: 'nominal',
            title: breakdown === 'account' ? 'Account' : 'User',
          },
        };

  const tooltip: Array<Record<string, unknown>> = [
    { field: 'date', type: 'temporal', title: 'Date', format: '%b %d, %Y' },
    { aggregate: 'sum', field: 'tokens', type: 'quantitative', title: 'Tokens', format: ',.0f' },
  ];
  if (breakdown !== 'none') {
    tooltip.push({
      field: breakdown,
      type: 'nominal',
      title: breakdown === 'account' ? 'Account' : 'User',
    });
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    data: { values: rows },
    mark: { type: 'area', interpolate: 'monotone', line: true, opacity: 0.5 },
    encoding: {
      x: { field: 'date', type: 'temporal', title: null, axis: { format: '%b %d' } },
      y: {
        aggregate: 'sum',
        field: 'tokens',
        type: 'quantitative',
        title: 'Tokens used',
        axis: { format: '~s' },
      },
      ...colorEncoding,
      tooltip,
    },
  };
}

interface SubscriptionTabProps {
  organizationId?: string;
}

export function SubscriptionTab({ organizationId = 'org-1' }: SubscriptionTabProps) {
  const accounts = useMemo(
    () => mockAccounts.filter((a) => a.organizationId === organizationId),
    [organizationId]
  );
  const users = mockAccountUsers;

  // Demo state for the current plan + this month's usage. In production these
  // would come from the org doc + a server-aggregated token counter.
  const tokenLimit = FREE_TOKEN_LIMIT;
  const tokensUsedThisMonth = 287_341;
  const usagePct = Math.min(100, (tokensUsedThisMonth / tokenLimit) * 100);
  const isExceeded = tokensUsedThisMonth >= tokenLimit;
  const usageBarColor = isExceeded
    ? '#F97066'
    : usagePct >= 75
      ? 'var(--color-amber-500)'
      : 'var(--color-teal-500)';

  const today = new Date();
  const [chartMonth, setChartMonth] = useState({ month: today.getMonth(), year: today.getFullYear() });
  const [breakdown, setBreakdown] = useState<Breakdown>('none');

  const dailyRows = useMemo(
    () => generateDailyUsage(chartMonth.year, chartMonth.month, accounts, users),
    [chartMonth, accounts, users]
  );
  const chartArtifact = useMemo(
    () => ({
      type: 'visualization' as const,
      spec: buildUsageSpec(dailyRows, breakdown),
      metadata: { title: 'Token usage' },
    }),
    [dailyRows, breakdown]
  );

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(720);
  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(([entry]) => {
      setChartWidth(Math.max(320, entry.contentRect.width));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [stopIndex, setStopIndex] = useState(0);
  const selectedStop = PRICING_STOPS[stopIndex];
  const nextStop = PRICING_STOPS[stopIndex + 1];
  const atMaxTier = stopIndex === MAX_STOP_INDEX;

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="mb-2">Current Plan</h2>
            <div className="flex items-center gap-3">
              <Badge
                className="text-base px-3 py-1"
                style={{
                  background: isExceeded ? '#F97066' : 'var(--color-teal-500)',
                  color: 'var(--color-text-inverse)',
                }}
              >
                {isExceeded ? 'Inactive' : 'Free'}
              </Badge>
              <span className="text-2xl font-bold">
                $0
                <span className="text-sm text-muted-foreground font-normal">/month</span>
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {formatNumber(tokenLimit)} tokens included per month · resets on {formatResetDate()}
            </p>
          </div>
          <Button onClick={() => setUpgradeOpen(true)}>
            <Sparkles className="size-4 mr-2" />
            Upgrade Subscription
          </Button>
        </div>

        {isExceeded && (
          <div className="mb-6 p-4 rounded-[var(--radius-md)] border-2 border-[#F97066] bg-[#F97066]/10 flex items-start gap-3">
            <AlertTriangle className="size-5 text-[#F97066] mt-0.5 shrink-0" />
            <div>
              <p className="font-bold mb-1">Token limit exceeded</p>
              <p className="text-sm text-muted-foreground">
                All accounts in this organization are inactive until your token allowance resets, or upgrade to a paid plan to keep working.
              </p>
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm">Token usage this month</p>
            <p className="text-sm font-bold">
              {formatNumber(tokensUsedThisMonth)}
              <span className="font-normal text-muted-foreground"> / {formatNumber(tokenLimit)}</span>
            </p>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div className="h-full transition-all" style={{ width: `${usagePct}%`, background: usageBarColor }} />
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="mb-1">Token Usage</h2>
            <p className="text-sm text-muted-foreground">Daily token consumption across the organization</p>
          </div>
          <div className="flex items-center gap-2">
            <MonthYearPicker
              month={chartMonth.month}
              year={chartMonth.year}
              onSelect={(m, y) => setChartMonth({ month: m, year: y })}
            />
            <Select value={breakdown} onValueChange={(v) => setBreakdown(v as Breakdown)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Break down by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No breakdown</SelectItem>
                <SelectItem value="account">By account</SelectItem>
                <SelectItem value="user">By user</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div ref={chartContainerRef} className="w-full">
          <ArtifactRenderer artifact={chartArtifact} width={chartWidth} height={320} />
        </div>
      </Card>

      <Dialog open={upgradeOpen} onOpenChange={setUpgradeOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Upgrade Subscription</DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            <div className="text-center py-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Selected plan</p>
              <p className="text-4xl font-bold mt-1">
                ${selectedStop.price}
                <span className="text-base text-muted-foreground font-normal">/month</span>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {formatNumber(selectedStop.tokens)} tokens per month
              </p>
            </div>

            <div>
              <Slider
                min={0}
                max={MAX_STOP_INDEX}
                step={1}
                value={[stopIndex]}
                onValueChange={([v]) => setStopIndex(v)}
              />
              <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                <span>
                  ${PRICING_STOPS[0].price} · {formatTokens(PRICING_STOPS[0].tokens)}
                </span>
                <span>
                  ${PRICING_STOPS[MAX_STOP_INDEX].price} · {formatTokens(PRICING_STOPS[MAX_STOP_INDEX].tokens)}
                </span>
              </div>
              {nextStop && (
                <p className="text-xs text-muted-foreground mt-3">
                  Next step: +{formatTokens(nextStop.tokens - selectedStop.tokens)} tokens for ${nextStop.price - selectedStop.price} more per month.
                </p>
              )}
            </div>

            {atMaxTier && (
              <div className="p-4 rounded-[var(--radius-md)] border-2 border-[var(--color-violet-300)] bg-[var(--color-violet-100)]/40">
                <p className="font-bold mb-1">Need a larger allowance?</p>
                <p className="text-sm text-muted-foreground mb-3">
                  For more than {formatTokens(PRICING_STOPS[MAX_STOP_INDEX].tokens)} tokens per month, switch to invoice billing with a custom token allowance.
                </p>
                <Button variant="outline" size="sm">
                  <MessageSquare className="size-4 mr-2" />
                  Contact Sales
                </Button>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setUpgradeOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setUpgradeOpen(false)}>Confirm Upgrade</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
