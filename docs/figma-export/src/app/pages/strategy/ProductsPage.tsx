import { Package, DollarSign, Star } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const products = [
  {
    name: 'Acme Platform — Starter',
    type: 'SaaS Subscription',
    price: '$49/mo',
    valueProps: ['5 users included', 'Core analytics dashboard', 'Email support'],
    status: 'active' as const,
  },
  {
    name: 'Acme Platform — Growth',
    type: 'SaaS Subscription',
    price: '$149/mo',
    valueProps: ['25 users included', 'Advanced analytics & reporting', 'API access', 'Priority support'],
    status: 'active' as const,
  },
  {
    name: 'Acme Platform — Enterprise',
    type: 'SaaS Subscription',
    price: 'Custom',
    valueProps: ['Unlimited users', 'Dedicated CSM', 'SSO & SCIM', 'Custom integrations', 'SLA guarantees'],
    status: 'active' as const,
  },
  {
    name: 'Acme Onboarding Workshop',
    type: 'Professional Service',
    price: '$2,500 one-time',
    valueProps: ['2-day implementation sprint', 'Data migration assistance', 'Team training'],
    status: 'active' as const,
  },
];

export function ProductsPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Products & Services</h2>
          <p className="text-sm text-muted-foreground">Offerings, pricing, and value propositions</p>
        </div>
        <Button variant="outline" size="sm">Add Product</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {products.map(product => (
          <Card key={product.name} className="p-5 flex flex-col">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div
                  className="size-10 rounded-[var(--radius-md)] bg-[var(--color-teal-500)] flex items-center justify-center shrink-0"
                  style={{ boxShadow: 'var(--shadow-color-teal)' }}
                >
                  <Package className="size-5 text-[var(--color-text-inverse)]" />
                </div>
                <div>
                  <p className="text-sm">{product.name}</p>
                  <p className="text-xs text-muted-foreground">{product.type}</p>
                </div>
              </div>
              <Badge variant="secondary">{product.status}</Badge>
            </div>

            <div className="flex items-center gap-1.5 mb-3 text-sm">
              <DollarSign className="size-3.5 text-[var(--color-teal-500)]" />
              <span>{product.price}</span>
            </div>

            <div className="space-y-1.5 flex-1">
              {product.valueProps.map(vp => (
                <div key={vp} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Star className="size-3 text-[var(--color-amber-400)] shrink-0" />
                  {vp}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}