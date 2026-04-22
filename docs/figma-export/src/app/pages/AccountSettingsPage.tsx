import { ConfigureIntegrationPanel } from '../components/ConfigureIntegrationPanel';
import { IntegrationIcon } from '../components/IntegrationIcon';
import { useState } from 'react';
import { Building2, Zap, Globe, AlertTriangle, DollarSign, Trash2 } from 'lucide-react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { mockIntegrations, Integration } from '../data/mockData';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Sheet, SheetContent } from '../components/ui/sheet';

export function AccountSettingsPage() {
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b p-4">
        <div>
          <h1 className="mb-1">Account Settings</h1>
          <p className="text-sm text-muted-foreground">
            Configure settings for your current account
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <Tabs defaultValue="general">
          <TabsList className="mb-6">
            <TabsTrigger value="general">
              <Building2 className="size-4 mr-2" />
              General
            </TabsTrigger>
            <TabsTrigger value="integrations">
              <Zap className="size-4 mr-2" />
              Integrations
            </TabsTrigger>
            <TabsTrigger value="channels">
              <Globe className="size-4 mr-2" />
              Channels
            </TabsTrigger>
            <TabsTrigger value="advanced">
              <AlertTriangle className="size-4 mr-2" />
              Advanced
            </TabsTrigger>
          </TabsList>

          <TabsContent value="general">
            <div className="space-y-6 max-w-3xl">
              <Card className="p-6">
                <h2 className="mb-4">Account Details</h2>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="account-name">Account Name</Label>
                    <Input 
                      id="account-name" 
                      defaultValue="US Market"
                      className="mt-1.5"
                    />
                    <p className="text-xs text-muted-foreground mt-1.5">
                      A descriptive name for this marketing account
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="industry">Industry</Label>
                    <Select defaultValue="saas">
                      <SelectTrigger id="industry" className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="saas">SaaS</SelectItem>
                        <SelectItem value="ecommerce">E-commerce</SelectItem>
                        <SelectItem value="retail">Retail</SelectItem>
                        <SelectItem value="healthcare">Healthcare</SelectItem>
                        <SelectItem value="finance">Finance</SelectItem>
                        <SelectItem value="education">Education</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="budget">Annual Advertising Budget</Label>
                    <div className="relative mt-1.5">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                      <Input 
                        id="budget"
                        type="number"
                        defaultValue="500000"
                        className="pl-9"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label htmlFor="account-status">Account Status</Label>
                      <p className="text-sm text-muted-foreground">
                        Active accounts are visible to all team members
                      </p>
                    </div>
                    <Switch id="account-status" defaultChecked />
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="mb-4">Regional Settings</h2>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="timezone">Timezone</Label>
                    <Select defaultValue="america-new-york">
                      <SelectTrigger id="timezone" className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="america-new-york">Eastern Time (ET)</SelectItem>
                        <SelectItem value="america-chicago">Central Time (CT)</SelectItem>
                        <SelectItem value="america-denver">Mountain Time (MT)</SelectItem>
                        <SelectItem value="america-los-angeles">Pacific Time (PT)</SelectItem>
                        <SelectItem value="europe-london">London (GMT)</SelectItem>
                        <SelectItem value="europe-paris">Paris (CET)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="data-region">Data Storage Region</Label>
                    <Select defaultValue="us">
                      <SelectTrigger id="data-region" className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="us">United States</SelectItem>
                        <SelectItem value="eu">Europe</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground mt-1.5">
                      Where your marketing data is stored for compliance
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="customer-region">Customer Region</Label>
                    <Select defaultValue="north-america">
                      <SelectTrigger id="customer-region" className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="north-america">North America</SelectItem>
                        <SelectItem value="south-america">South America</SelectItem>
                        <SelectItem value="europe">Europe</SelectItem>
                        <SelectItem value="asia">Asia</SelectItem>
                        <SelectItem value="global">Global</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="integrations">
            <div className="space-y-6">
              <div>
                <h2 className="mb-1">Active Integrations</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Connect your marketing tools to enable AI-powered automation
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {mockIntegrations.map(integration => {
                    const statusMap = {
                      connected: { label: 'Connected', dot: 'bg-[var(--color-success)]', text: 'text-[var(--color-success-text)]', bg: 'bg-[var(--color-success-bg)]' },
                      disconnected: { label: 'Not Connected', dot: 'bg-[var(--color-error)]', text: 'text-[var(--color-error-text)]', bg: 'bg-[var(--color-error-bg)]' },
                      error: { label: 'Issue', dot: 'bg-[var(--color-warning)]', text: 'text-[var(--color-warning-text)]', bg: 'bg-[var(--color-warning-bg)]' },
                    };
                    const s = statusMap[integration.status];
                    return (
                    <Card key={integration.id} className="p-4 cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedIntegration(integration)}>
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <IntegrationIcon name={integration.name} fallbackEmoji={integration.icon} />
                          <div>
                            <h3>{integration.name}</h3>
                            <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full mt-1 ${s.bg}`}>
                              <span className={`size-1.5 rounded-full ${s.dot}`} />
                              <span className={`text-xs ${s.text}`} style={{ fontWeight: 600 }}>{s.label}</span>
                            </div>
                          </div>
                        </div>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={(e) => { e.stopPropagation(); setSelectedIntegration(integration); }}
                        >
                          Configure
                        </Button>
                      </div>
                    </Card>
                    );
                  })}
                </div>
              </div>

              <div>
                <h2 className="mb-3">Available Integrations</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {['Shopify', 'Google Search Console'].map(name => (
                    <Card key={name} className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <IntegrationIcon name={name} fallbackEmoji="🔌" className="size-8" />
                          <div>
                            <h3>{name}</h3>
                            <p className="text-xs text-muted-foreground">
                              Not connected
                            </p>
                          </div>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => setSelectedIntegration({
                          id: `available-${name.toLowerCase().replace(/\s+/g, '-')}`,
                          name,
                          status: 'disconnected',
                          icon: '🔌',
                        })}>
                          Connect
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

              <div>
                <h2 className="mb-3">Coming Soon</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {['Bing Ads'].map(name => (
                    <Card key={name} className="p-4 opacity-60">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <IntegrationIcon name={name} fallbackEmoji="🔌" className="size-8" />
                          <div>
                            <h3>{name}</h3>
                            <p className="text-xs text-muted-foreground">
                              Coming soon
                            </p>
                          </div>
                        </div>
                        <Button variant="outline" size="sm" disabled>
                          Notify Me
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="channels">
            <div className="space-y-6 max-w-3xl">
              <Card className="p-6">
                <h2 className="mb-4">Company Websites</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Domains owned by your company
                </p>
                <div className="space-y-3 mb-4">
                  {['example.com', 'shop.example.com', 'blog.example.com'].map((domain) => (
                    <div key={domain} className="flex items-center justify-between p-3 rounded-md bg-muted/50">
                      <div className="flex items-center gap-2">
                        <Globe className="size-4 text-muted-foreground" />
                        <span className="font-mono text-sm">{domain}</span>
                      </div>
                      <Button variant="ghost" size="sm">
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <Button variant="outline" size="sm">
                  Add Website
                </Button>
              </Card>

              <Card className="p-6">
                <h2 className="mb-4">Marketing Channels</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Select the channels you use for marketing
                </p>
                <div className="space-y-3">
                  {[
                    'Email Marketing',
                    'Paid Search (Google Ads)',
                    'Social Media (Organic)',
                    'Social Media (Paid)',
                    'Content Marketing / SEO',
                    'Events & Webinars',
                    'Display Advertising',
                    'Affiliate Marketing'
                  ].map((channel) => (
                    <div key={channel} className="flex items-center justify-between">
                      <Label htmlFor={`channel-${channel}`}>{channel}</Label>
                      <Switch id={`channel-${channel}`} defaultChecked={channel.includes('Email') || channel.includes('Paid')} />
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="advanced">
            <div className="space-y-6 max-w-3xl">
              <Card className="p-6 border-amber-500/50">
                <div className="flex items-start gap-3 mb-4">
                  <AlertTriangle className="size-5 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <h2 className="mb-1 text-amber-500">Transfer Account</h2>
                    <p className="text-sm text-muted-foreground">
                      Move this account to a different organization. This cannot be undone.
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="target-org">Target Organization</Label>
                    <Select>
                      <SelectTrigger id="target-org" className="mt-1.5">
                        <SelectValue placeholder="Select organization..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="org-2">ACME Global</SelectItem>
                        <SelectItem value="org-3">TechStart Inc.</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button variant="outline">
                    Transfer Account
                  </Button>
                </div>
              </Card>

              <Card className="p-6 border-destructive/50">
                <div className="flex items-start gap-3 mb-4">
                  <Trash2 className="size-5 text-destructive shrink-0 mt-0.5" />
                  <div>
                    <h2 className="mb-1 text-destructive">Delete Account</h2>
                    <p className="text-sm text-muted-foreground">
                      Permanently delete this account and all its data. This action cannot be undone.
                    </p>
                  </div>
                </div>
                <Button variant="destructive">
                  Delete Account
                </Button>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <Sheet open={selectedIntegration !== null} onOpenChange={() => setSelectedIntegration(null)}>
        <SheetContent className="sm:max-w-md p-0 gap-0">
          {selectedIntegration && (
            <ConfigureIntegrationPanel 
              integration={selectedIntegration} 
              onClose={() => setSelectedIntegration(null)} 
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}