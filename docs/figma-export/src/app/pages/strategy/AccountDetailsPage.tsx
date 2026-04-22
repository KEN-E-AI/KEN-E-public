import { Building2, Globe, Calendar, MapPin } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const accountData = {
  company: 'Acme Corp',
  industry: 'B2B SaaS',
  founded: '2019',
  headquarters: 'San Francisco, CA',
  website: 'www.acmecorp.io',
  employees: '50–200',
  annualRevenue: '$5M–$15M ARR',
  objectives: [
    'Increase MQL volume by 40% in Q1 2026',
    'Reduce CAC by 15% across paid channels',
    'Expand into mid-market segment',
    'Launch EMEA go-to-market motion',
  ],
};

export function AccountDetailsPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Account Details</h2>
          <p className="text-sm text-muted-foreground">Company information and business objectives</p>
        </div>
        <Button variant="outline" size="sm">Edit</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 space-y-4">
          <h3 className="text-sm flex items-center gap-2">
            <Building2 className="size-4 text-[var(--color-blue-500)]" />
            Company Profile
          </h3>
          <div className="space-y-3">
            {[
              { label: 'Company', value: accountData.company },
              { label: 'Industry', value: accountData.industry },
              { label: 'Employees', value: accountData.employees },
              { label: 'Annual Revenue', value: accountData.annualRevenue },
            ].map(item => (
              <div key={item.label} className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">{item.label}</span>
                <span className="text-sm">{item.value}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5 space-y-4">
          <h3 className="text-sm flex items-center gap-2">
            <Globe className="size-4 text-[var(--color-teal-500)]" />
            Details
          </h3>
          <div className="space-y-3">
            {[
              { icon: Calendar, label: 'Founded', value: accountData.founded },
              { icon: MapPin, label: 'HQ', value: accountData.headquarters },
              { icon: Globe, label: 'Website', value: accountData.website },
            ].map(item => (
              <div key={item.label} className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <item.icon className="size-3" />
                  {item.label}
                </span>
                <span className="text-sm">{item.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5 space-y-4">
        <h3 className="text-sm">Business Objectives</h3>
        <div className="space-y-2">
          {accountData.objectives.map((obj, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)]">
              <Badge variant="outline" className="shrink-0 mt-0.5">{i + 1}</Badge>
              <p className="text-sm">{obj}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
