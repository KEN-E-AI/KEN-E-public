import { 
  Building2, 
  CreditCard, 
  Users, 
  DollarSign,
  Package,
  FileText,
  Plus,
  Plug,
  Check,
  ExternalLink
} from 'lucide-react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { mockAccounts } from '../data/mockData';

export function OrganizationSettingsPage() {
  return (
    <div className="max-w-5xl mx-auto p-6">
      <Tabs defaultValue="general">
        <TabsList className="mb-6">
          <TabsTrigger value="general">
            <Building2 className="size-4 mr-2" />
            General
          </TabsTrigger>
          <TabsTrigger value="subscription">
            <Package className="size-4 mr-2" />
            Subscription
          </TabsTrigger>
          <TabsTrigger value="billing">
            <CreditCard className="size-4 mr-2" />
            Billing
          </TabsTrigger>
          <TabsTrigger value="team">
            <Users className="size-4 mr-2" />
            Team
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Plug className="size-4 mr-2" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="accounts">
            <Building2 className="size-4 mr-2" />
            Accounts
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card className="p-6">
            <h2 className="mb-4">Organization Details</h2>
            <div className="space-y-4 max-w-xl">
              <div>
                <Label htmlFor="org-name">Organization Name</Label>
                <Input 
                  id="org-name" 
                  defaultValue="ACME Corporation"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  This is your organization's visible name within KEN-E
                </p>
              </div>

              <div>
                <Label htmlFor="org-slug">Organization Slug</Label>
                <Input 
                  id="org-slug" 
                  defaultValue="acme-corp"
                  className="mt-1.5 font-mono"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Used in URLs and API calls
                </p>
              </div>

              <div className="pt-4">
                <Button>Save Changes</Button>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="subscription">
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="mb-2">Current Plan</h2>
                  <div className="flex items-center gap-3">
                    <Badge 
                      className="text-base px-3 py-1"
                      style={{
                        background: 'var(--color-violet-500)',
                        color: 'var(--color-text-inverse)'
                      }}
                    >
                      Professional
                    </Badge>
                    <span className="text-2xl font-bold">$299<span className="text-sm text-muted-foreground font-normal">/month</span></span>
                  </div>
                </div>
                <Button>Upgrade Plan</Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="p-4 rounded-lg bg-muted/50">
                  <p className="text-sm text-muted-foreground mb-1">Accounts</p>
                  <p className="text-2xl font-bold">3 <span className="text-sm text-muted-foreground font-normal">/ 10</span></p>
                </div>
                <div className="p-4 rounded-lg bg-muted/50">
                  <p className="text-sm text-muted-foreground mb-1">Team Members</p>
                  <p className="text-2xl font-bold">8 <span className="text-sm text-muted-foreground font-normal">/ 25</span></p>
                </div>
                <div className="p-4 rounded-lg bg-muted/50">
                  <p className="text-sm text-muted-foreground mb-1">AI Sessions</p>
                  <p className="text-2xl font-bold">142 <span className="text-sm text-muted-foreground font-normal">/ ∞</span></p>
                </div>
              </div>

              <div>
                <h3 className="mb-3">Plan Features</h3>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <div className="size-1.5 rounded-full bg-[var(--color-violet-500)]" />
                    Up to 10 marketing accounts
                  </li>
                  <li className="flex items-center gap-2">
                    <div className="size-1.5 rounded-full bg-[var(--color-violet-500)]" />
                    25 team members
                  </li>
                  <li className="flex items-center gap-2">
                    <div className="size-1.5 rounded-full bg-[var(--color-violet-500)]" />
                    Unlimited AI sessions
                  </li>
                  <li className="flex items-center gap-2">
                    <div className="size-1.5 rounded-full bg-[var(--color-violet-500)]" />
                    Advanced analytics & reporting
                  </li>
                  <li className="flex items-center gap-2">
                    <div className="size-1.5 rounded-full bg-[var(--color-violet-500)]" />
                    Priority support
                  </li>
                </ul>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Usage This Month</h2>
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm">AI Sessions</p>
                    <p className="text-sm font-bold">142 sessions</p>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-[var(--color-violet-500)]"
                      style={{ width: '35%' }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm">API Calls</p>
                    <p className="text-sm font-bold">24,582 / 100,000</p>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-[var(--color-blue-500)]"
                      style={{ width: '25%' }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm">Data Storage</p>
                    <p className="text-sm font-bold">8.2 GB / 50 GB</p>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-[var(--color-teal-500)]"
                      style={{ width: '16%' }}
                    />
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="billing">
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-4">Payment Method</h2>
              <div className="flex items-center justify-between p-4 rounded-lg border-2">
                <div className="flex items-center gap-3">
                  <div className="size-12 rounded bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <CreditCard className="size-6 text-white" />
                  </div>
                  <div>
                    <p className="font-bold">•••• •••• •••• 4242</p>
                    <p className="text-sm text-muted-foreground">Expires 12/2025</p>
                  </div>
                </div>
                <Button variant="outline" size="sm">Update</Button>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2>Billing Information</h2>
                <Button variant="outline" size="sm">Edit</Button>
              </div>
              <div className="space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-muted-foreground mb-1">Company Name</p>
                    <p className="font-medium">ACME Corporation</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Email</p>
                    <p className="font-medium">billing@acme.com</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Address</p>
                    <p className="font-medium">123 Main St, San Francisco, CA 94105</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Tax ID</p>
                    <p className="font-medium">US-12-3456789</p>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2>Invoice History</h2>
                <Button variant="outline" size="sm">
                  <FileText className="size-4 mr-2" />
                  Download All
                </Button>
              </div>
              <div className="space-y-2">
                {[
                  { date: 'Feb 1, 2026', amount: '$299.00', status: 'Paid', invoice: 'INV-2026-02' },
                  { date: 'Jan 1, 2026', amount: '$299.00', status: 'Paid', invoice: 'INV-2026-01' },
                  { date: 'Dec 1, 2025', amount: '$299.00', status: 'Paid', invoice: 'INV-2025-12' },
                  { date: 'Nov 1, 2025', amount: '$299.00', status: 'Paid', invoice: 'INV-2025-11' },
                ].map((invoice) => (
                  <div key={invoice.invoice} className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-4">
                      <div>
                        <p className="font-medium">{invoice.invoice}</p>
                        <p className="text-sm text-muted-foreground">{invoice.date}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <p className="font-bold">{invoice.amount}</p>
                      <Badge variant="secondary">{invoice.status}</Badge>
                      <Button variant="ghost" size="sm">
                        <FileText className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="team">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="mb-1">Organization Team</h2>
                <p className="text-sm text-muted-foreground">
                  Manage who can access organization settings and accounts
                </p>
              </div>
              <Button>
                <Plus className="size-4 mr-2" />
                Invite Member
              </Button>
            </div>

            <div className="space-y-2">
              {[
                { name: 'Sarah Chen', email: 'sarah@acme.com', role: 'Owner', avatar: 'SC' },
                { name: 'Mike Rodriguez', email: 'mike@acme.com', role: 'Admin', avatar: 'MR' },
                { name: 'Emma Thompson', email: 'emma@acme.com', role: 'Admin', avatar: 'ET' },
                { name: 'David Park', email: 'david@acme.com', role: 'Member', avatar: 'DP' },
                { name: 'Lisa Wang', email: 'lisa@acme.com', role: 'Member', avatar: 'LW' },
              ].map((member) => (
                <div key={member.email} className="flex items-center justify-between p-4 rounded-lg hover:bg-muted/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold text-sm">
                      {member.avatar}
                    </div>
                    <div>
                      <p className="font-medium">{member.name}</p>
                      <p className="text-sm text-muted-foreground">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">{member.role}</Badge>
                    {member.role !== 'Owner' && (
                      <Button variant="ghost" size="sm">
                        Edit
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="integrations">
          <div className="space-y-6">
            <Card className="p-6">
              <div className="mb-6">
                <h2 className="mb-1">Available Integrations</h2>
                <p className="text-sm text-muted-foreground">
                  Connect third-party tools to extend KEN-E's capabilities
                </p>
              </div>

              <div className="space-y-4">
                {/* Slack Integration - Connected */}
                <div className="flex items-start justify-between p-5 rounded-lg border-2 bg-muted/20">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-white flex items-center justify-center shrink-0">
                      <svg className="size-8" viewBox="0 0 24 24" fill="none">
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#36C5F0"/>
                        <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834z" fill="#2EB67D"/>
                        <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834z" fill="#ECB22E"/>
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-bold">Slack</h3>
                        <Badge 
                          className="gap-1"
                          style={{
                            background: 'var(--color-teal-500)',
                            color: 'var(--color-text-inverse)'
                          }}
                        >
                          <Check className="size-3" />
                          Connected
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-3">
                        Receive notifications and updates from KEN-E directly in your Slack workspace
                      </p>
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <div className="size-1.5 rounded-full bg-current" />
                          <span>Workspace: <span className="font-medium text-foreground">ACME Team</span></span>
                        </div>
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <div className="size-1.5 rounded-full bg-current" />
                          <span>Channel: <span className="font-medium text-foreground">#marketing-updates</span></span>
                        </div>
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <div className="size-1.5 rounded-full bg-current" />
                          <span>Connected: <span className="font-medium text-foreground">Feb 10, 2026</span></span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      Configure
                    </Button>
                    <Button variant="ghost" size="sm">
                      Disconnect
                    </Button>
                  </div>
                </div>

                {/* Microsoft Teams - Available */}
                <div className="flex items-start justify-between p-5 rounded-lg border-2 hover:bg-muted/20 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-white flex items-center justify-center shrink-0">
                      <svg className="size-8" viewBox="0 0 24 24" fill="none">
                        <rect x="1" y="1" width="22" height="22" rx="2" fill="#5059C9"/>
                        <path d="M17.5 12c0 1.933-1.567 3.5-3.5 3.5s-3.5-1.567-3.5-3.5 1.567-3.5 3.5-3.5 3.5 1.567 3.5 3.5z" fill="white"/>
                        <path d="M13 8.5h8V12h-8z" fill="white" opacity="0.5"/>
                        <path d="M13 12h8v3.5h-8z" fill="white" opacity="0.75"/>
                        <path d="M3 8.5h8V12H3z" fill="white" opacity="0.5"/>
                        <path d="M3 12h8v3.5H3z" fill="white" opacity="0.75"/>
                      </svg>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Microsoft Teams</h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Share campaign insights and collaborate with your team in Microsoft Teams
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="outline" className="text-xs">Coming Soon</Badge>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" disabled>
                    Connect
                  </Button>
                </div>

                {/* Zapier - Available */}
                <div className="flex items-start justify-between p-5 rounded-lg border-2 hover:bg-muted/20 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-[#FF4A00] flex items-center justify-center shrink-0">
                      <span className="text-white font-bold text-lg">Z</span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Zapier</h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Automate workflows by connecting KEN-E with 5,000+ apps
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <ExternalLink className="size-3" />
                        <a href="#" className="hover:underline">View available Zaps</a>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Connect
                  </Button>
                </div>

                {/* Webhooks */}
                <div className="flex items-start justify-between p-5 rounded-lg border-2 hover:bg-muted/20 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center shrink-0">
                      <Plug className="size-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Webhooks</h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Send real-time data to your custom endpoints when events occur
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <ExternalLink className="size-3" />
                        <a href="#" className="hover:underline">View API documentation</a>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Configure
                  </Button>
                </div>
              </div>
            </Card>

            {/* Integration Settings for Slack */}
            <Card className="p-6">
              <h2 className="mb-4">Slack Notification Settings</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Choose what notifications to send to your Slack workspace
              </p>

              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <input 
                    type="checkbox" 
                    id="slack-campaigns"
                    defaultChecked
                    className="mt-1"
                  />
                  <div>
                    <Label htmlFor="slack-campaigns" className="font-medium cursor-pointer">
                      Campaign Alerts
                    </Label>
                    <p className="text-sm text-muted-foreground mt-1">
                      Notify about campaign performance anomalies and important changes
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <input 
                    type="checkbox" 
                    id="slack-ai"
                    defaultChecked
                    className="mt-1"
                  />
                  <div>
                    <Label htmlFor="slack-ai" className="font-medium cursor-pointer">
                      AI Recommendations
                    </Label>
                    <p className="text-sm text-muted-foreground mt-1">
                      Share KEN-E's optimization suggestions with your team
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <input 
                    type="checkbox" 
                    id="slack-reports"
                    className="mt-1"
                  />
                  <div>
                    <Label htmlFor="slack-reports" className="font-medium cursor-pointer">
                      Daily Performance Reports
                    </Label>
                    <p className="text-sm text-muted-foreground mt-1">
                      Receive daily summaries of account performance
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <input 
                    type="checkbox" 
                    id="slack-team"
                    defaultChecked
                    className="mt-1"
                  />
                  <div>
                    <Label htmlFor="slack-team" className="font-medium cursor-pointer">
                      Team Activity
                    </Label>
                    <p className="text-sm text-muted-foreground mt-1">
                      Updates when team members make significant changes
                    </p>
                  </div>
                </div>
              </div>

              <div className="pt-6">
                <Button>Save Notification Settings</Button>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="accounts">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="mb-1">Marketing Accounts</h2>
                <p className="text-sm text-muted-foreground">
                  Accounts within this organization
                </p>
              </div>
              <Button>
                <Plus className="size-4 mr-2" />
                Add Account
              </Button>
            </div>

            <div className="space-y-3">
              {mockAccounts.map((account) => (
                <div key={account.id} className="flex items-center justify-between p-4 rounded-lg border-2">
                  <div className="flex items-center gap-3">
                    <Building2 className="size-8 text-muted-foreground" />
                    <div>
                      <p className="font-bold">{account.name}</p>
                      <p className="text-sm text-muted-foreground capitalize">
                        Your role: {account.role}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">Active</Badge>
                    <Button variant="outline" size="sm">
                      Manage
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}