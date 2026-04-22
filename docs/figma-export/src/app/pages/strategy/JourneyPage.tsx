import { Route, Eye, MousePointerClick, ShoppingCart, Heart, ArrowRight } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const stages = [
  {
    name: 'Awareness',
    icon: Eye,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    channels: ['Organic Search', 'Social Media', 'Content Marketing', 'PR'],
    touchpoints: ['Blog posts', 'LinkedIn articles', 'Podcast appearances', 'Industry reports'],
    kpis: ['Impressions', 'Website traffic', 'Brand search volume'],
    conversionRate: '3.2%',
  },
  {
    name: 'Consideration',
    icon: MousePointerClick,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    channels: ['Email Nurture', 'Retargeting', 'Webinars', 'Case Studies'],
    touchpoints: ['Product demo page', 'Comparison guides', 'Customer testimonials', 'Free trial'],
    kpis: ['MQLs', 'Demo requests', 'Content downloads'],
    conversionRate: '12.5%',
  },
  {
    name: 'Decision',
    icon: ShoppingCart,
    color: 'var(--color-teal-500)',
    shadow: 'var(--shadow-color-teal)',
    channels: ['Sales Outreach', 'Product Demo', 'ROI Calculator', 'Proposal'],
    touchpoints: ['1:1 demo call', 'Pricing page', 'Security documentation', 'Contract negotiation'],
    kpis: ['SQLs', 'Win rate', 'Deal velocity'],
    conversionRate: '28%',
  },
  {
    name: 'Retention',
    icon: Heart,
    color: 'var(--color-amber-500)',
    shadow: '0 4px 16px rgba(245, 158, 11, 0.25)',
    channels: ['Onboarding', 'Customer Success', 'In-app Education', 'Community'],
    touchpoints: ['Welcome sequence', 'QBRs', 'Feature announcements', 'User community'],
    kpis: ['NPS', 'Churn rate', 'Expansion revenue'],
    conversionRate: '92% retention',
  },
];

export function JourneyPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Customer Journey</h2>
          <p className="text-sm text-muted-foreground">Touchpoints, funnel stages, and lifecycle mapping</p>
        </div>
        <Button variant="outline" size="sm">Edit Journey</Button>
      </div>

      {/* Stage Flow */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {stages.map((stage, i) => (
          <div key={stage.name} className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-2 px-4 py-2 rounded-[var(--radius-pill)] border-2 border-[var(--color-border-default)] bg-card">
              <div
                className="size-6 rounded-[var(--radius-sm)] flex items-center justify-center"
                style={{ backgroundColor: stage.color }}
              >
                <stage.icon className="size-3.5 text-[var(--color-text-inverse)]" />
              </div>
              <span className="text-xs">{stage.name}</span>
              <Badge variant="outline" className="text-[10px]">{stage.conversionRate}</Badge>
            </div>
            {i < stages.length - 1 && (
              <ArrowRight className="size-4 text-muted-foreground shrink-0" />
            )}
          </div>
        ))}
      </div>

      {/* Stage Details */}
      <div className="space-y-4">
        {stages.map(stage => (
          <Card key={stage.name} className="p-5">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="size-10 rounded-[var(--radius-md)] flex items-center justify-center shrink-0 -rotate-2"
                style={{ backgroundColor: stage.color, boxShadow: stage.shadow }}
              >
                <stage.icon className="size-5 text-[var(--color-text-inverse)]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm">{stage.name}</p>
                  <Badge variant="secondary">{stage.conversionRate}</Badge>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-2">Channels</p>
                <div className="flex flex-wrap gap-1.5">
                  {stage.channels.map(ch => (
                    <Badge key={ch} variant="outline" className="text-[10px]">{ch}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">Key Touchpoints</p>
                <div className="space-y-1">
                  {stage.touchpoints.map(tp => (
                    <p key={tp} className="text-xs">{tp}</p>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">KPIs</p>
                <div className="flex flex-wrap gap-1.5">
                  {stage.kpis.map(kpi => (
                    <Badge key={kpi} variant="secondary" className="text-[10px]">{kpi}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
