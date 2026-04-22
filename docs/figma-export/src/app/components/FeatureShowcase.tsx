import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { QuickStartGuide } from './QuickStartGuide';
import { 
  MessageSquare, 
  Calendar, 
  Workflow, 
  BarChart3, 
  FlaskConical,
  Lightbulb,
  Zap,
  Users,
  TrendingUp
} from 'lucide-react';

export function FeatureShowcase() {
  const features = [
    {
      icon: MessageSquare,
      title: 'AI Chat Interface',
      description: 'Primary control surface with concurrent session support',
      color: 'var(--color-blue-500)',
      accentColor: 'var(--color-accent-slot-1)',
      highlights: ['Natural language commands', '2-3 simultaneous sessions', 'Context-aware responses']
    },
    {
      icon: Calendar,
      title: 'Marketing Calendar',
      description: 'Unified view of campaigns across all channels',
      color: 'var(--color-teal-500)',
      accentColor: 'var(--color-accent-slot-5)',
      highlights: ['Month/week/day views', 'Color-coded channels', 'Drag-and-drop scheduling']
    },
    {
      icon: Workflow,
      title: 'Workflows & Automation',
      description: 'Freeform automations and scheduled dashboards',
      color: 'var(--color-violet-500)',
      accentColor: 'var(--color-accent-slot-3)',
      highlights: ['Automation builder', 'Dashboard refresh schedules', 'Visual previews']
    },
    {
      icon: BarChart3,
      title: 'Performance Analytics',
      description: 'Real-time metrics with AI recommendations',
      color: 'var(--color-amber-500)',
      accentColor: 'var(--color-accent-slot-2)',
      highlights: ['Key metric tracking', 'Trend visualizations', 'Actionable insights']
    },
    {
      icon: FlaskConical,
      title: 'AI Simulations',
      description: 'Focus groups and campaign forecasting',
      color: 'var(--color-slate-500)',
      accentColor: 'var(--color-accent-slot-1)',
      highlights: ['100-agent focus groups', 'Scenario modeling', 'Before/after comparisons']
    },
    {
      icon: Zap,
      title: 'Integrations Hub',
      description: 'Connect your martech stack',
      color: 'var(--color-blue-500)',
      accentColor: 'var(--color-accent-slot-5)',
      highlights: ['Google Ads, HubSpot, Meta', 'Real-time sync', 'Status monitoring']
    }
  ];

  const layoutOptions = [
    {
      name: 'Layout A: Split View',
      description: 'Chat-dominant 50-60% left panel with icon sidebar',
      best: 'Power users, large screens',
      accentColor: 'var(--color-accent-slot-1)',
    },
    {
      name: 'Layout B: Drawer',
      description: 'Full-width content with floating chat overlay',
      best: 'Content-focused workflows',
      accentColor: 'var(--color-accent-slot-2)',
    },
    {
      name: 'Layout C: Hub',
      description: 'Top navigation with collapsible bottom chat',
      best: 'Clean, minimal preference',
      accentColor: 'var(--color-accent-slot-3)',
    }
  ];

  return (
    <div className="space-y-10 p-6">
      <QuickStartGuide />
      
      <div>
        <h2 
          className="mb-6 text-[var(--text-display-md)]"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Core Features
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <Card key={feature.title} className="p-6" accentColor={feature.accentColor}>
              <div 
                className="size-12 rounded-[var(--radius-md)] flex items-center justify-center mb-4 -rotate-2"
                style={{ 
                  backgroundColor: `${feature.color}20`,
                  color: feature.color,
                }}
              >
                <feature.icon className="size-6" />
              </div>
              <h3 
                className="mb-2 text-[var(--text-heading-md)]"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {feature.title}
              </h3>
              <p className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)] mb-4">
                {feature.description}
              </p>
              <div className="space-y-2">
                {feature.highlights.map((highlight) => (
                  <div key={highlight} className="flex items-center gap-2 text-[var(--text-body-sm)]">
                    <div className="size-1.5 rounded-full" style={{ backgroundColor: feature.color }} />
                    <span className="text-[var(--color-text-tertiary)]">{highlight}</span>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h2 
          className="mb-6 text-[var(--text-display-md)]"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Layout Options
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {layoutOptions.map((layout) => (
            <Card key={layout.name} className="p-6" accentColor={layout.accentColor}>
              <h3 
                className="mb-2 text-[var(--text-heading-md)]"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {layout.name}
              </h3>
              <p className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)] mb-4">
                {layout.description}
              </p>
              <Badge variant="info">
                {layout.best}
              </Badge>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h2 
          className="mb-6 text-[var(--text-display-md)]"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Design Principles
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-6" accentColor="var(--color-accent-slot-1)">
            <h3 
              className="mb-4 text-[var(--text-heading-md)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Soft Maximalism
            </h3>
            <ul className="space-y-2 text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
              <li>• Modern sans-serif typography (Plus Jakarta Sans)</li>
              <li>• Moderate rounded corners</li>
              <li>• Colorful accents and gradients</li>
              <li>• Ambient background effects</li>
            </ul>
          </Card>
          <Card className="p-6" accentColor="var(--color-accent-slot-3)">
            <h3 
              className="mb-4 text-[var(--text-heading-md)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Productivity-Focused
            </h3>
            <ul className="space-y-2 text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
              <li>• AI-first interaction model</li>
              <li>• Quick actions and shortcuts</li>
              <li>• Session management</li>
              <li>• Consistent navigation patterns</li>
            </ul>
          </Card>
          <Card className="p-6" accentColor="var(--color-accent-slot-5)">
            <h3 
              className="mb-4 text-[var(--text-heading-md)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Fully Responsive
            </h3>
            <ul className="space-y-2 text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
              <li>• Mobile-optimized layouts</li>
              <li>• Bottom tab navigation on mobile</li>
              <li>• Touch-friendly interactions</li>
              <li>• Adaptive component sizing</li>
            </ul>
          </Card>
          <Card className="p-6" accentColor="var(--color-accent-slot-2)">
            <h3 
              className="mb-4 text-[var(--text-heading-md)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Dark Mode Ready
            </h3>
            <ul className="space-y-2 text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
              <li>• Warm dark backgrounds</li>
              <li>• Optimized contrast ratios</li>
              <li>• Smooth theme transitions</li>
              <li>• System preference support</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}