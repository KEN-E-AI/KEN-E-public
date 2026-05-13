import { 
  User, 
  Mail, 
  Briefcase, 
  Image, 
  Bell, 
  Lock,
  Shield,
  Globe,
  Upload,
  AlertCircle,
  CheckCircle2,
  Type
} from 'lucide-react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { useState, useEffect } from 'react';

export function UserSettingsPage() {
  // In a real app, this would come from organization settings context/state
  const isSlackConnectedToOrg = true; // Simulating Slack is connected at org level
  const isTeamsConnectedToOrg = false; // Simulating Teams is NOT connected at org level
  const isOrgEditor = false; // Simulating user is NOT an organization editor

  const [profilePicture, setProfilePicture] = useState('SC');
  const [firstName, setFirstName] = useState('Sarah');
  const [lastName, setLastName] = useState('Chen');
  const [email, setEmail] = useState('sarah@company.com');
  const [jobTitle, setJobTitle] = useState('Marketing Director');
  const [slackUsername, setSlackUsername] = useState('@sarah.chen');
  const [teamsUsername, setTeamsUsername] = useState('sarah.chen@company.com');

  // Chat text size preference
  const [chatTextSize, setChatTextSize] = useState<'small' | 'medium' | 'large'>('medium');

  // Load chat text size from localStorage on mount
  useEffect(() => {
    try {
      const savedSize = localStorage.getItem('kene-chat-text-size') as 'small' | 'medium' | 'large';
      if (savedSize) {
        setChatTextSize(savedSize);
      }
    } catch {
      // localStorage may not be available in sandboxed environments
    }
  }, []);

  // Save chat text size to localStorage when it changes
  const handleChatTextSizeChange = (value: string) => {
    const size = value as 'small' | 'medium' | 'large';
    setChatTextSize(size);
    try {
      localStorage.setItem('kene-chat-text-size', size);
    } catch {
      // localStorage may not be available in sandboxed environments
    }
    // Dispatch event to notify ChatInterface of the change
    window.dispatchEvent(new CustomEvent('kene-chat-text-size-change', { detail: size }));
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <Tabs defaultValue="profile">
        <TabsList className="mb-6">
          <TabsTrigger value="profile">
            <User className="size-4 mr-2" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="size-4 mr-2" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="size-4 mr-2" />
            Security
          </TabsTrigger>
          <TabsTrigger value="preferences">
            <Globe className="size-4 mr-2" />
            Preferences
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-4">Profile Picture</h2>
              <div className="flex items-center gap-6">
                <div className="size-24 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold text-3xl">
                  {profilePicture}
                </div>
                <div>
                  <Button variant="outline" className="mb-2">
                    <Upload className="size-4 mr-2" />
                    Upload Photo
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    JPG, PNG or GIF. Max size 2MB.
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Personal Information</h2>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="first-name">First Name</Label>
                    <Input 
                      id="first-name" 
                      defaultValue={firstName}
                      className="mt-1.5"
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="last-name">Last Name</Label>
                    <Input 
                      id="last-name" 
                      defaultValue={lastName}
                      className="mt-1.5"
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="email">Email Address</Label>
                  <Input 
                    id="email" 
                    type="email"
                    defaultValue={email}
                    className="mt-1.5"
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Your email is used for login and notifications
                  </p>
                </div>

                <div>
                  <Label htmlFor="job-title">Job Title</Label>
                  <Input 
                    id="job-title" 
                    defaultValue={jobTitle}
                    className="mt-1.5"
                    onChange={(e) => setJobTitle(e.target.value)}
                  />
                </div>

                <div className="pt-4">
                  <Button>Save Changes</Button>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Integration Usernames</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Connect your accounts to receive notifications across different platforms
              </p>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="slack-username">Slack Username</Label>
                  <Input 
                    id="slack-username" 
                    placeholder="@sarah.chen"
                    defaultValue={slackUsername}
                    className="mt-1.5"
                    disabled={!isSlackConnectedToOrg}
                    onChange={(e) => setSlackUsername(e.target.value)}
                  />
                  {isSlackConnectedToOrg ? (
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                      <CheckCircle2 className="size-3 text-[var(--color-teal-500)]" />
                      <span>Slack is connected to your organization</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                      <AlertCircle className="size-3 text-[var(--color-coral)]" />
                      <span>Slack must be enabled by an organization editor in Organization Settings</span>
                    </div>
                  )}
                </div>

                <div>
                  <Label htmlFor="teams-username">Microsoft Teams Username</Label>
                  <Input 
                    id="teams-username" 
                    placeholder="sarah.chen@company.com"
                    className="mt-1.5"
                    disabled={!isTeamsConnectedToOrg}
                    onChange={(e) => setTeamsUsername(e.target.value)}
                  />
                  {isTeamsConnectedToOrg ? (
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                      <CheckCircle2 className="size-3 text-[var(--color-teal-500)]" />
                      <span>Microsoft Teams is connected to your organization</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                      <AlertCircle className="size-3 text-[var(--color-coral)]" />
                      <span>Microsoft Teams must be enabled by an organization editor in Organization Settings</span>
                    </div>
                  )}
                </div>

                <div className="pt-4">
                  <Button disabled={!isSlackConnectedToOrg && !isTeamsConnectedToOrg}>
                    Save Integration Settings
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="notifications">
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-1">Notification Channels</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Choose where you want to receive notifications
              </p>

              <div className="space-y-4">
                {/* KEN-E - Always enabled */}
                <div className="flex items-start justify-between p-4 rounded-lg border-2 bg-muted/20">
                  <div className="flex items-start gap-3">
                    <input 
                      type="checkbox" 
                      id="channel-kene"
                      defaultChecked
                      disabled
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <Label htmlFor="channel-kene" className="font-medium cursor-not-allowed">
                        KEN-E (In-App)
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        Receive notifications within the KEN-E platform
                      </p>
                      <div className="flex items-center gap-1.5 mt-2">
                        <Badge 
                          variant="secondary"
                          className="text-xs"
                          style={{
                            background: 'var(--color-violet-500)',
                            color: 'var(--color-text-inverse)'
                          }}
                        >
                          Required
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Email */}
                <div className="flex items-start justify-between p-4 rounded-lg border-2 hover:bg-muted/20 transition-colors">
                  <div className="flex items-start gap-3">
                    <input 
                      type="checkbox" 
                      id="channel-email"
                      defaultChecked
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <Label htmlFor="channel-email" className="font-medium cursor-pointer">
                        Email
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        Receive notifications via email at <span className="font-medium text-foreground">sarah@company.com</span>
                      </p>
                      <p className="text-xs text-muted-foreground mt-2">
                        Update your email address in the Profile tab
                      </p>
                    </div>
                  </div>
                </div>

                {/* Slack */}
                <div className={`flex items-start justify-between p-4 rounded-lg border-2 transition-colors ${isSlackConnectedToOrg ? 'hover:bg-muted/20' : 'opacity-60'}`}>
                  <div className="flex items-start gap-3">
                    <input 
                      type="checkbox" 
                      id="channel-slack"
                      defaultChecked={isSlackConnectedToOrg}
                      disabled={!isSlackConnectedToOrg}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <Label htmlFor="channel-slack" className={`font-medium ${isSlackConnectedToOrg ? 'cursor-pointer' : 'cursor-not-allowed'}`}>
                        Slack
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        {isSlackConnectedToOrg 
                          ? 'Receive notifications in Slack as @sarah.chen'
                          : 'Send notifications to your Slack account'
                        }
                      </p>
                      {isSlackConnectedToOrg ? (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                          <CheckCircle2 className="size-3 text-[var(--color-teal-500)]" />
                          <span>Connected • Update username in Profile tab</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                          <AlertCircle className="size-3 text-[var(--color-coral)]" />
                          <span>Slack must be enabled by an organization editor in Organization Settings</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Microsoft Teams */}
                <div className={`flex items-start justify-between p-4 rounded-lg border-2 transition-colors ${isTeamsConnectedToOrg ? 'hover:bg-muted/20' : 'opacity-60'}`}>
                  <div className="flex items-start gap-3">
                    <input 
                      type="checkbox" 
                      id="channel-teams"
                      disabled={!isTeamsConnectedToOrg}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <Label htmlFor="channel-teams" className={`font-medium ${isTeamsConnectedToOrg ? 'cursor-pointer' : 'cursor-not-allowed'}`}>
                        Microsoft Teams
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        Send notifications to your Microsoft Teams account
                      </p>
                      {isTeamsConnectedToOrg ? (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                          <CheckCircle2 className="size-3 text-[var(--color-teal-500)]" />
                          <span>Connected • Update username in Profile tab</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                          <AlertCircle className="size-3 text-[var(--color-coral)]" />
                          <span>Microsoft Teams must be enabled by an organization editor in Organization Settings</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-1">Notification Preferences</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Choose which channels to use for each notification type. All notifications appear in KEN-E.
              </p>

              <div className="space-y-8">
                {/* Session Management */}
                <div>
                  <h3 className="mb-4">Session Management</h3>
                  
                  {/* Header Row */}
                  <div 
                    className="grid gap-4 mb-3 pb-3 border-b-2"
                    style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                  >
                    <div className="text-sm font-medium text-muted-foreground">Notification Type</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">KEN-E</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Email</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Slack</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Teams</div>
                  </div>

                  {/* Notification Rows */}
                  <div className="space-y-3">
                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Inactive Session</p>
                        <p className="text-sm text-muted-foreground">When work is completed in a session that is inactive</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Scheduled Jobs */}
                <div>
                  <h3 className="mb-4">Scheduled Jobs</h3>
                  
                  {/* Header Row */}
                  <div 
                    className="grid gap-4 mb-3 pb-3 border-b-2"
                    style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                  >
                    <div className="text-sm font-medium text-muted-foreground">Notification Type</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">KEN-E</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Email</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Slack</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Teams</div>
                  </div>

                  {/* Notification Rows */}
                  <div className="space-y-3">
                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Analysis</p>
                        <p className="text-sm text-muted-foreground">A new analysis is ready for review or hit an error</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Dashboard Refresh</p>
                        <p className="text-sm text-muted-foreground">A dashboard has successfully refreshed or hit an error</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Workflow</p>
                        <p className="text-sm text-muted-foreground">A scheduled workflow has successfully refreshed or hit an error</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Channels */}
                <div>
                  <h3 className="mb-4">Channels</h3>
                  
                  {/* Header Row */}
                  <div 
                    className="grid gap-4 mb-3 pb-3 border-b-2"
                    style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                  >
                    <div className="text-sm font-medium text-muted-foreground">Notification Type</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">KEN-E</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Email</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Slack</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Teams</div>
                  </div>

                  {/* Notification Rows */}
                  <div className="space-y-3">
                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Organic Search</p>
                        <p className="text-sm text-muted-foreground">We have identified an issue with organic search that needs attention</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Paid Media</p>
                        <p className="text-sm text-muted-foreground">We have identified an issue with paid media (paid search, display, video, etc) that needs attention</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Email</p>
                        <p className="text-sm text-muted-foreground">We have identified an issue with email that needs attention</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Social</p>
                        <p className="text-sm text-muted-foreground">We have identified an issue with social media that needs attention</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Analytics</p>
                        <p className="text-sm text-muted-foreground">We have identified an issue with web/app analytics that needs attention</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isTeamsConnectedToOrg} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Organization Management */}
                <div className={!isOrgEditor ? 'opacity-50' : ''}>
                  <div className="flex items-center gap-2 mb-4">
                    <h3>Organization Management</h3>
                    {!isOrgEditor && (
                      <Badge variant="outline" className="text-xs">
                        Requires Organization Editor Role
                      </Badge>
                    )}
                  </div>
                  
                  {/* Header Row */}
                  <div 
                    className="grid gap-4 mb-3 pb-3 border-b-2"
                    style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                  >
                    <div className="text-sm font-medium text-muted-foreground">Notification Type</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">KEN-E</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Email</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Slack</div>
                    <div className="text-sm font-medium text-muted-foreground text-center">Teams</div>
                  </div>

                  {/* Notification Rows */}
                  <div className="space-y-3">
                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Monthly Usage is Above 75%</p>
                        <p className="text-sm text-muted-foreground">Your organization's monthly usage has exceeded 75% of the limit</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isOrgEditor} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Monthly Usage is Maxed Out</p>
                        <p className="text-sm text-muted-foreground">Your organization's monthly usage has reached the maximum limit</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isOrgEditor} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isOrgEditor || !isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Billing Problem</p>
                        <p className="text-sm text-muted-foreground">There was a problem charging your credit card</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isOrgEditor} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isTeamsConnectedToOrg} />
                      </div>
                    </div>

                    <div 
                      className="grid gap-4 items-start"
                      style={{ gridTemplateColumns: '1fr 6.25rem 6.25rem 6.25rem 6.25rem' }}
                    >
                      <div>
                        <p className="font-medium">Integration Request</p>
                        <p className="text-sm text-muted-foreground">A team member is requesting that you add an integration</p>
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked disabled className="size-4" />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" defaultChecked className="size-4" disabled={!isOrgEditor} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isSlackConnectedToOrg} />
                      </div>
                      <div className="flex justify-center">
                        <input type="checkbox" className="size-4" disabled={!isOrgEditor || !isTeamsConnectedToOrg} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 mt-6 border-t-2">
                <Button>Save Notification Preferences</Button>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="security">
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-4">Password</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Update your password to keep your account secure
              </p>
              <div className="space-y-4 max-w-md">
                <div>
                  <Label htmlFor="current-password">Current Password</Label>
                  <Input 
                    id="current-password" 
                    type="password"
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label htmlFor="new-password">New Password</Label>
                  <Input 
                    id="new-password" 
                    type="password"
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label htmlFor="confirm-password">Confirm New Password</Label>
                  <Input 
                    id="confirm-password" 
                    type="password"
                    className="mt-1.5"
                  />
                </div>
                <Button>Update Password</Button>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-start gap-3 mb-4">
                <Shield className="size-5 text-[var(--color-violet-500)] shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h2 className="mb-1">Two-Factor Authentication</h2>
                  <p className="text-sm text-muted-foreground mb-4">
                    Add an extra layer of security to your account
                  </p>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="text-muted-foreground">
                      Not Enabled
                    </Badge>
                    <Button>Enable 2FA</Button>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Active Sessions</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Manage your active sessions across different devices
              </p>
              <div className="space-y-3">
                {[
                  { device: 'MacBook Pro', location: 'San Francisco, CA', lastActive: '2 minutes ago', current: true },
                  { device: 'iPhone 14', location: 'San Francisco, CA', lastActive: '1 hour ago', current: false },
                  { device: 'Chrome on Windows', location: 'New York, NY', lastActive: '2 days ago', current: false },
                ].map((session, index) => (
                  <div key={index} className="flex items-center justify-between p-4 rounded-lg border-2">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-medium">{session.device}</p>
                        {session.current && (
                          <Badge 
                            variant="secondary"
                            style={{
                              background: 'var(--color-violet-500)',
                              color: 'var(--color-text-inverse)'
                            }}
                          >
                            Current
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {session.location} • Last active {session.lastActive}
                      </p>
                    </div>
                    {!session.current && (
                      <Button variant="ghost" size="sm">
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="preferences">
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-4">Language & Region</h2>
              <div className="space-y-4 max-w-md">
                <div>
                  <Label htmlFor="language">Preferred Language</Label>
                  <Select defaultValue="en">
                    <SelectTrigger id="language" className="mt-1.5">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="es">Español</SelectItem>
                      <SelectItem value="fr">Français</SelectItem>
                      <SelectItem value="de">Deutsch</SelectItem>
                      <SelectItem value="ja">日本語</SelectItem>
                      <SelectItem value="zh">中文</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

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
                  <Label htmlFor="date-format">Date Format</Label>
                  <Select defaultValue="mm-dd-yyyy">
                    <SelectTrigger id="date-format" className="mt-1.5">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mm-dd-yyyy">MM/DD/YYYY</SelectItem>
                      <SelectItem value="dd-mm-yyyy">DD/MM/YYYY</SelectItem>
                      <SelectItem value="yyyy-mm-dd">YYYY-MM-DD</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="pt-4">
                  <Button>Save Preferences</Button>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Interface Preferences</h2>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="chat-text-size">Chat Text Size</Label>
                  <Select value={chatTextSize} onValueChange={handleChatTextSizeChange}>
                    <SelectTrigger id="chat-text-size" className="mt-1.5 max-w-md">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="small">Small</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="large">Large</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-muted-foreground mt-1.5">
                    <Type className="size-3.5 inline mr-1" />
                    Adjust the size of text in chat messages for better readability
                  </p>
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label htmlFor="keyboard-shortcuts">Keyboard Shortcuts</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable keyboard shortcuts for faster navigation
                    </p>
                  </div>
                  <Switch id="keyboard-shortcuts" defaultChecked />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label htmlFor="animations">Animations</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable interface animations and transitions
                    </p>
                  </div>
                  <Switch id="animations" defaultChecked />
                </div>
              </div>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}