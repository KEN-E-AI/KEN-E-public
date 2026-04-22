import { Swords, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const competitors = [
  {
    name: 'RivalCo',
    positioning: 'Enterprise-first, feature-heavy platform',
    strengths: ['Brand recognition', 'Enterprise sales team', 'Deep integrations'],
    weaknesses: ['Complex onboarding', 'Higher price point', 'Slow innovation'],
    trend: 'up' as const,
    threatLevel: 'high' as const,
  },
  {
    name: 'StartupXYZ',
    positioning: 'PLG-driven, developer-friendly tool',
    strengths: ['Modern UX', 'Fast iteration', 'Strong community'],
    weaknesses: ['Limited enterprise features', 'Small sales team', 'Narrow use case'],
    trend: 'up' as const,
    threatLevel: 'medium' as const,
  },
  {
    name: 'LegacySoft',
    positioning: 'Established player with broad feature set',
    strengths: ['Market share', 'Distribution partnerships', 'Compliance certs'],
    weaknesses: ['Outdated UI', 'Technical debt', 'Slow support'],
    trend: 'down' as const,
    threatLevel: 'low' as const,
  },
];

const TrendIcon = ({ trend }: { trend: 'up' | 'down' | 'flat' }) => {
  if (trend === 'up') return <TrendingUp className="size-3 text-[var(--color-error)]" />;
  if (trend === 'down') return <TrendingDown className="size-3 text-[var(--color-success)]" />;
  return <Minus className="size-3 text-muted-foreground" />;
};

export function CompetitorsPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Competitors</h2>
          <p className="text-sm text-muted-foreground">Competitive landscape and positioning analysis</p>
        </div>
        <Button variant="outline" size="sm">Add Competitor</Button>
      </div>

      <div className="space-y-4">
        {competitors.map(comp => (
          <Card key={comp.name} className="p-5">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div
                  className="size-10 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center"
                  style={{ boxShadow: 'var(--shadow-color-violet)' }}
                >
                  <Swords className="size-5 text-[var(--color-text-inverse)]" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm">{comp.name}</p>
                    <Badge
                      variant={comp.threatLevel === 'high' ? 'destructive' : comp.threatLevel === 'medium' ? 'default' : 'secondary'}
                    >
                      {comp.threatLevel} threat
                    </Badge>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <TrendIcon trend={comp.trend} />
                      {comp.trend === 'up' ? 'Growing' : comp.trend === 'down' ? 'Declining' : 'Stable'}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{comp.positioning}</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-2">Strengths</p>
                <div className="space-y-1.5">
                  {comp.strengths.map(s => (
                    <div key={s} className="text-xs px-2.5 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]">
                      {s}
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">Weaknesses</p>
                <div className="space-y-1.5">
                  {comp.weaknesses.map(w => (
                    <div key={w} className="text-xs px-2.5 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]">
                      {w}
                    </div>
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