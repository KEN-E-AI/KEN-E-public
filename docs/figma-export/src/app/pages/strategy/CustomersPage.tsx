import { Users, Briefcase, MapPin, DollarSign } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const personas = [
  {
    name: 'Marketing Manager Maya',
    segment: 'Mid-Market',
    title: 'Head of Marketing',
    company: '200–1,000 employees',
    location: 'US & Canada',
    budget: '$50K–$200K annual martech spend',
    painPoints: ['Scattered data across tools', 'Manual reporting overhead', 'Proving ROI to leadership'],
    goals: ['Unified analytics dashboard', 'Automated campaign workflows', 'Clear attribution model'],
  },
  {
    name: 'Growth Lead Greg',
    segment: 'Startup / Scale-up',
    title: 'VP Growth',
    company: '50–200 employees',
    location: 'Global, English-speaking',
    budget: '$20K–$80K annual martech spend',
    painPoints: ['Limited team bandwidth', 'Rapid experimentation needs', 'Budget constraints'],
    goals: ['AI-powered content creation', 'Fast A/B testing', 'Self-serve onboarding'],
  },
  {
    name: 'Enterprise Emma',
    segment: 'Enterprise',
    title: 'Director of Digital Marketing',
    company: '1,000+ employees',
    location: 'North America & EMEA',
    budget: '$500K+ annual martech spend',
    painPoints: ['Cross-team coordination', 'Compliance & governance', 'Legacy system integration'],
    goals: ['SSO & role-based access', 'Custom integrations', 'Dedicated account management'],
  },
];

export function CustomersPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Customers</h2>
          <p className="text-sm text-muted-foreground">Target audiences, personas, and segmentation</p>
        </div>
        <Button variant="outline" size="sm">Add Persona</Button>
      </div>

      <div className="space-y-4">
        {personas.map(persona => (
          <Card key={persona.name} className="p-5">
            <div className="flex items-start gap-4 mb-4">
              <div
                className="size-11 rounded-[var(--radius-md)] bg-[var(--color-blue-500)] flex items-center justify-center shrink-0"
                style={{ boxShadow: 'var(--shadow-color-blue)' }}
              >
                <Users className="size-5 text-[var(--color-text-inverse)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-sm">{persona.name}</p>
                  <Badge variant="secondary">{persona.segment}</Badge>
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Briefcase className="size-3" />{persona.title}</span>
                  <span className="flex items-center gap-1"><MapPin className="size-3" />{persona.location}</span>
                  <span className="flex items-center gap-1"><DollarSign className="size-3" />{persona.budget}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-2">Pain Points</p>
                <div className="space-y-1.5">
                  {persona.painPoints.map(p => (
                    <div key={p} className="text-xs px-2.5 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]">
                      {p}
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">Goals</p>
                <div className="space-y-1.5">
                  {persona.goals.map(g => (
                    <div key={g} className="text-xs px-2.5 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]">
                      {g}
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