import { Lightbulb, TrendingUp, AlertTriangle, Zap, Clock } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const insights = [
  {
    id: 'ins-1',
    title: 'LinkedIn engagement outperforms other channels by 3.2x',
    description: 'Analysis of the last 90 days shows LinkedIn posts generate 3.2x more MQLs per dollar spent compared to Google Ads. Consider reallocating 10-15% of paid search budget to LinkedIn campaigns.',
    category: 'Channel Optimization',
    impact: 'high' as const,
    type: 'opportunity' as const,
    generatedAt: new Date(2026, 1, 14),
    actionable: true,
  },
  {
    id: 'ins-2',
    title: 'Blog content decay: 12 high-traffic posts losing rankings',
    description: 'SEO monitoring detected 12 blog posts that have dropped from page 1 to page 2 in the last 30 days. These posts collectively drove 8,200 monthly visits. Updating content and refreshing publish dates could recover traffic.',
    category: 'Content',
    impact: 'high' as const,
    type: 'risk' as const,
    generatedAt: new Date(2026, 1, 13),
    actionable: true,
  },
  {
    id: 'ins-3',
    title: 'Trial-to-paid conversion spike from in-app onboarding flow',
    description: 'Users who complete the new interactive onboarding (launched Jan 20) convert at 34% vs 18% baseline. This suggests expanding guided experiences to other product areas could improve overall conversion.',
    category: 'Conversion',
    impact: 'high' as const,
    type: 'trend' as const,
    generatedAt: new Date(2026, 1, 12),
    actionable: false,
  },
  {
    id: 'ins-4',
    title: 'Email open rates declining in EMEA segment',
    description: 'EMEA email open rates have dropped from 28% to 19% over 60 days. Possible causes: send-time optimization needed, subject line fatigue, or list hygiene issues. Recommend A/B testing send times and re-engagement campaign.',
    category: 'Email',
    impact: 'medium' as const,
    type: 'risk' as const,
    generatedAt: new Date(2026, 1, 11),
    actionable: true,
  },
  {
    id: 'ins-5',
    title: 'Competitor RivalCo launched a free tier product',
    description: 'RivalCo announced a free-forever plan targeting SMBs yesterday. This could impact our Starter tier positioning. Consider launching a competitive response: either a limited free tier or enhanced Starter value proposition.',
    category: 'Competitive',
    impact: 'high' as const,
    type: 'risk' as const,
    generatedAt: new Date(2026, 1, 10),
    actionable: true,
  },
  {
    id: 'ins-6',
    title: 'Webinar series driving highest-quality SQLs',
    description: 'SQLs originating from webinar attendees have a 42% close rate vs 22% average. Monthly webinars are producing disproportionate pipeline value. Recommend increasing frequency to bi-weekly.',
    category: 'Channel Optimization',
    impact: 'medium' as const,
    type: 'opportunity' as const,
    generatedAt: new Date(2026, 1, 9),
    actionable: true,
  },
];

const typeConfig = {
  opportunity: { color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success-bg)]', icon: TrendingUp, label: 'Opportunity' },
  risk: { color: 'text-[var(--color-error)]', bg: 'bg-[var(--color-error-bg)]', icon: AlertTriangle, label: 'Risk' },
  trend: { color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info-bg)]', icon: Zap, label: 'Trend' },
};

export function InsightsPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Insights</h2>
          <p className="text-sm text-muted-foreground">AI-generated findings, trends, and strategic recommendations</p>
        </div>
        <Button variant="outline" size="sm" className="gap-2">
          <Zap className="size-3.5" />
          Generate New
        </Button>
      </div>

      <div className="space-y-3">
        {insights.map(insight => {
          const config = typeConfig[insight.type];
          return (
            <Card key={insight.id} className="p-5">
              <div className="flex items-start gap-4">
                <div
                  className={`size-10 rounded-[var(--radius-md)] flex items-center justify-center shrink-0 ${config.bg}`}
                >
                  <config.icon className={`size-5 ${config.color}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <p className="text-sm">{insight.title}</p>
                  </div>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <Badge variant={insight.impact === 'high' ? 'default' : 'secondary'}>
                      {insight.impact} impact
                    </Badge>
                    <Badge variant="outline">{config.label}</Badge>
                    <Badge variant="outline">{insight.category}</Badge>
                    <span className="flex items-center gap-1 text-[0.625rem] text-muted-foreground">
                      <Clock className="size-2.5" />
                      {insight.generatedAt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{insight.description}</p>
                </div>

                {insight.actionable && (
                  <div className="flex gap-2 shrink-0">
                    <Button size="sm" variant="default">Act</Button>
                    <Button size="sm" variant="outline">Dismiss</Button>
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}