import { Gauge, TrendingUp, TrendingDown, Target } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const metricCategories = [
  {
    category: 'Acquisition',
    metrics: [
      { name: 'Monthly Website Visitors', current: '142K', target: '200K', trend: 'up' as const, status: 'on-track' as const },
      { name: 'Marketing Qualified Leads (MQLs)', current: '485', target: '600', trend: 'up' as const, status: 'on-track' as const },
      { name: 'Cost Per Lead (CPL)', current: '$38', target: '$30', trend: 'down' as const, status: 'at-risk' as const },
      { name: 'Organic Traffic Share', current: '62%', target: '70%', trend: 'up' as const, status: 'on-track' as const },
    ],
  },
  {
    category: 'Conversion',
    metrics: [
      { name: 'MQL → SQL Rate', current: '28%', target: '35%', trend: 'up' as const, status: 'at-risk' as const },
      { name: 'Demo-to-Close Rate', current: '22%', target: '25%', trend: 'flat' as const, status: 'on-track' as const },
      { name: 'Average Deal Size', current: '$18.5K', target: '$20K', trend: 'up' as const, status: 'on-track' as const },
      { name: 'Sales Cycle Length', current: '42 days', target: '35 days', trend: 'down' as const, status: 'at-risk' as const },
    ],
  },
  {
    category: 'Retention & Expansion',
    metrics: [
      { name: 'Net Revenue Retention', current: '112%', target: '120%', trend: 'up' as const, status: 'on-track' as const },
      { name: 'Monthly Churn Rate', current: '2.1%', target: '1.5%', trend: 'down' as const, status: 'at-risk' as const },
      { name: 'NPS Score', current: '52', target: '60', trend: 'up' as const, status: 'on-track' as const },
      { name: 'Customer Lifetime Value', current: '$42K', target: '$50K', trend: 'up' as const, status: 'on-track' as const },
    ],
  },
];

const TrendIcon = ({ trend }: { trend: 'up' | 'down' | 'flat' }) => {
  if (trend === 'up') return <TrendingUp className="size-3" />;
  if (trend === 'down') return <TrendingDown className="size-3" />;
  return <span className="text-[10px]">—</span>;
};

export function MetricsPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Metrics</h2>
          <p className="text-sm text-muted-foreground">KPIs, benchmarks, and performance targets</p>
        </div>
        <Button variant="outline" size="sm">Add Metric</Button>
      </div>

      {metricCategories.map(cat => (
        <div key={cat.category} className="space-y-3">
          <h3 className="text-sm flex items-center gap-2">
            <Gauge className="size-4 text-[var(--color-blue-500)]" />
            {cat.category}
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {cat.metrics.map(metric => (
              <Card key={metric.name} className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <p className="text-xs text-muted-foreground">{metric.name}</p>
                  <Badge
                    variant={metric.status === 'on-track' ? 'secondary' : 'destructive'}
                    className="text-[10px] capitalize"
                  >
                    {metric.status}
                  </Badge>
                </div>
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-lg">{metric.current}</p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                      <Target className="size-3" />
                      Target: {metric.target}
                    </div>
                  </div>
                  <div className={`flex items-center gap-1 text-xs ${
                    metric.trend === 'up' ? 'text-[var(--color-success)]' : 
                    metric.trend === 'down' ? 'text-[var(--color-error)]' : 'text-muted-foreground'
                  }`}>
                    <TrendIcon trend={metric.trend} />
                    {metric.trend}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
