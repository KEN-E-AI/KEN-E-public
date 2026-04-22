import { Target, Megaphone, Mail, Search, Share2, PenTool } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const strategies = [
  {
    name: 'Content-Led Growth',
    description: 'Build authority through high-value content that drives organic traffic and nurtures prospects through the funnel.',
    icon: PenTool,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    status: 'active' as const,
    channels: ['Blog', 'SEO', 'LinkedIn', 'YouTube'],
    tactics: [
      'Publish 3 long-form articles per week',
      'Monthly industry research report',
      'Weekly LinkedIn thought-leadership posts',
      'Quarterly webinar series',
    ],
    budget: '35% of total',
  },
  {
    name: 'Paid Acquisition',
    description: 'Targeted advertising campaigns to capture high-intent demand and accelerate pipeline.',
    icon: Megaphone,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    status: 'active' as const,
    channels: ['Google Ads', 'LinkedIn Ads', 'Meta Ads'],
    tactics: [
      'Brand search defense campaigns',
      'Competitor targeting on LinkedIn',
      'Retargeting for demo page visitors',
      'Lookalike audiences from closed-won deals',
    ],
    budget: '40% of total',
  },
  {
    name: 'Email & Lifecycle',
    description: 'Automated nurture sequences and lifecycle campaigns to convert and retain customers.',
    icon: Mail,
    color: 'var(--color-teal-500)',
    shadow: 'var(--shadow-color-teal)',
    status: 'active' as const,
    channels: ['Email', 'In-app messaging'],
    tactics: [
      '7-email welcome sequence for trial signups',
      'Monthly newsletter with curated insights',
      'Behavioral trigger emails (feature adoption)',
      'Win-back campaigns for churned users',
    ],
    budget: '10% of total',
  },
  {
    name: 'SEO & Organic',
    description: 'Technical and content SEO to capture search demand across the buyer journey.',
    icon: Search,
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    status: 'planning' as const,
    channels: ['Google Search', 'YouTube', 'App stores'],
    tactics: [
      'Pillar page strategy for top 5 keywords',
      'Technical SEO audit and fixes',
      'Internal linking optimization',
      'Schema markup for rich snippets',
    ],
    budget: '10% of total',
  },
  {
    name: 'Partnerships & Co-Marketing',
    description: 'Strategic partnerships with complementary tools and influencers to expand reach.',
    icon: Share2,
    color: 'var(--color-violet-500)',
    shadow: 'var(--shadow-color-violet)',
    status: 'planning' as const,
    channels: ['Partner ecosystem', 'Events', 'Integrations marketplace'],
    tactics: [
      'Co-webinars with integration partners',
      'Joint case studies with key customers',
      'Influencer gifting program',
      'Marketplace listing optimization',
    ],
    budget: '5% of total',
  },
];

export function MarketingPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Marketing Strategies</h2>
          <p className="text-sm text-muted-foreground">Channel mix, campaign frameworks, and growth levers</p>
        </div>
        <Button variant="outline" size="sm">Add Strategy</Button>
      </div>

      <div className="space-y-4">
        {strategies.map(strategy => (
          <Card key={strategy.name} className="p-5">
            <div className="flex items-start gap-4 mb-4">
              <div
                className="size-10 rounded-[var(--radius-md)] flex items-center justify-center shrink-0"
                style={{ backgroundColor: strategy.color, boxShadow: strategy.shadow }}
              >
                <strategy.icon className="size-5 text-[var(--color-text-inverse)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-sm">{strategy.name}</p>
                  <Badge variant={strategy.status === 'active' ? 'default' : 'secondary'} className="capitalize">
                    {strategy.status}
                  </Badge>
                  <Badge variant="outline">{strategy.budget}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{strategy.description}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-2">Channels</p>
                <div className="flex flex-wrap gap-1.5">
                  {strategy.channels.map(ch => (
                    <Badge key={ch} variant="outline" className="text-[10px]">{ch}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">Key Tactics</p>
                <div className="space-y-1">
                  {strategy.tactics.map(t => (
                    <div key={t} className="flex items-start gap-2 text-xs">
                      <Target className="size-3 text-muted-foreground shrink-0 mt-0.5" />
                      {t}
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