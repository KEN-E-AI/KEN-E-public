import { Link } from 'react-router';
import {
  Building2,
  Swords,
  Package,
  Users,
  Palette,
  Route,
  Target,
  Gauge,
  Lightbulb,
  ArrowRight,
} from 'lucide-react';
import { Badge } from '../../components/ui/badge';

const sections = [
  {
    name: 'Account Details',
    description: 'Company information, industry, and business objectives',
    href: '/strategy/account-details',
    icon: Building2,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Competitors',
    description: 'Competitive landscape, positioning, and market analysis',
    href: '/strategy/competitors',
    icon: Swords,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Products & Services',
    description: 'Offerings, pricing tiers, and value propositions',
    href: '/strategy/products',
    icon: Package,
    color: 'var(--color-teal-500)',
    shadow: 'var(--shadow-color-teal)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Customers',
    description: 'Target audiences, personas, and segmentation',
    href: '/strategy/customers',
    icon: Users,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Brand Guidelines',
    description: 'Voice, tone, visual identity, and messaging framework',
    href: '/strategy/brand',
    icon: Palette,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Customer Journey',
    description: 'Touchpoints, funnel stages, and lifecycle mapping',
    href: '/strategy/journey',
    icon: Route,
    color: 'var(--color-teal-500)',
    shadow: 'var(--shadow-color-teal)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Marketing Strategies',
    description: 'Channel mix, campaign frameworks, and growth levers',
    href: '/strategy/marketing',
    icon: Target,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Metrics',
    description: 'KPIs, benchmarks, and performance targets',
    href: '/strategy/metrics',
    icon: Gauge,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    rotation: '',
    badge: null,
  },
  {
    name: 'Insights',
    description: 'AI-generated findings, trends, and strategic recommendations',
    href: '/strategy/insights',
    icon: Lightbulb,
    color: 'var(--color-amber-500)',
    shadow: '0 4px 16px rgba(245, 158, 11, 0.25)',
    rotation: '',
    badge: 'AI-Powered',
  },
];

export function StrategyIndex() {
  return (
    <div className="px-6 pb-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sections.map((section) => (
          <Link
            key={section.name}
            to={section.href}
            className="group block"
          >
            <div
              className="relative p-5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-1 transition-all cursor-pointer bg-card h-full"
              style={{
                transitionTimingFunction: 'var(--ease-bounce)',
                transitionDuration: 'var(--duration-fast)',
              }}
            >
              <div className="flex items-start gap-4">
                <div
                  className={`size-11 rounded-[var(--radius-md)] flex items-center justify-center shrink-0 ${section.rotation}`}
                  style={{
                    backgroundColor: section.color,
                    boxShadow: section.shadow,
                  }}
                >
                  <section.icon className="size-5 text-[var(--color-text-inverse)]" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <p className="text-sm">{section.name}</p>
                    {section.badge && (
                      <Badge variant="secondary" className="text-[0.625rem] px-1.5 py-0">
                        {section.badge}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {section.description}
                  </p>
                </div>

                <ArrowRight
                  className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all shrink-0 mt-1"
                  style={{
                    transitionTimingFunction: 'var(--ease-bounce)',
                    transitionDuration: 'var(--duration-fast)',
                  }}
                />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}