import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Sparkles, Zap, Target, TrendingUp } from 'lucide-react';

export function QuickStartGuide() {
  const steps = [
    {
      icon: Sparkles,
      title: 'Start with the AI Chat',
      description: 'Ask the AI to help you create campaigns, analyze data, or set up automations',
      example: '"Create a product launch email campaign for next month"',
      color: 'text-violet-500'
    },
    {
      icon: Target,
      title: 'Explore the Calendar',
      description: 'View all your marketing activities across channels in one unified calendar',
      tip: 'Click on any day to add new activities or view details',
      color: 'text-blue-500'
    },
    {
      icon: Zap,
      title: 'Create Workflows',
      description: 'Automate repetitive tasks and schedule dashboard refreshes',
      tip: 'Start with pre-built templates or create custom automations',
      color: 'text-green-500'
    },
    {
      icon: TrendingUp,
      title: 'Monitor Performance',
      description: 'Track key metrics and receive AI-powered optimization recommendations',
      tip: 'Accept or dismiss recommendations to improve your campaigns',
      color: 'text-amber-500'
    }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-2">Quick Start Guide</h2>
        <p className="text-muted-foreground">
          Get started with KEN-E in 4 simple steps
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {steps.map((step, index) => (
          <Card key={index} className="p-4">
            <div className="flex items-start gap-3 mb-3">
              <div className={`p-2 rounded-lg bg-muted`}>
                <step.icon className={`size-5 ${step.color}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-xs">
                    Step {index + 1}
                  </Badge>
                </div>
                <h3 className="mb-2">{step.title}</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  {step.description}
                </p>
                {step.example && (
                  <div className="p-2 bg-muted rounded text-xs font-mono">
                    {step.example}
                  </div>
                )}
                {step.tip && (
                  <p className="text-xs text-muted-foreground mt-2">
                    💡 {step.tip}
                  </p>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}