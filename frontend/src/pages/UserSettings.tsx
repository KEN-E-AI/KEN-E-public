import { useState, useEffect } from "react";
import axios from "axios";
import {
  User,
  Bell,
  Shield,
  Globe,
  Upload,
  AlertCircle,
  CheckCircle2,
  Type,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { NotificationPreferences } from "@/components/notifications/NotificationPreferences";

const UserSettings = () => {
  const { toast } = useToast();
  const { user, updateUser } = useAuth();
  const [profile, setProfile] = useState({
    firstName: user?.firstName || "",
    lastName: user?.lastName || "",
    email: user?.email || "",
    jobTitle: user?.jobTitle || "",
  });

  const [chatTextSize, setChatTextSize] = useState<
    "small" | "medium" | "large"
  >("medium");

  useEffect(() => {
    try {
      const raw = localStorage.getItem("kene-chat-text-size");
      const valid = ["small", "medium", "large"] as const;
      if (valid.includes(raw as (typeof valid)[number])) {
        setChatTextSize(raw as (typeof valid)[number]);
      }
    } catch {
      // localStorage unavailable in sandboxed environments
    }
  }, []);

  if (!user) return <div>Loading...</div>;

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setProfile({ ...profile, [e.target.id]: e.target.value });
  };

  const saveProfile = async () => {
    try {
      await axios.put(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/users/${encodeURIComponent(user.id)}?account_id=${encodeURIComponent(user.id)}`,
        {
          profile: {
            first_name: profile.firstName,
            last_name: profile.lastName,
            email: profile.email,
            job_title: profile.jobTitle,
          },
        },
      );

      updateUser({
        firstName: profile.firstName,
        lastName: profile.lastName,
        email: profile.email,
        jobTitle: profile.jobTitle,
      });

      toast({ title: "Success", description: "Profile saved successfully!" });
    } catch (error) {
      console.error("Error saving profile:", error);
      toast({
        title: "Error",
        description: "Failed to save profile.",
        variant: "destructive",
      });
    }
  };

  const handleChatTextSizeChange = (value: string) => {
    const size = value as "small" | "medium" | "large";
    setChatTextSize(size);
    try {
      localStorage.setItem("kene-chat-text-size", size);
    } catch {
      // localStorage unavailable in sandboxed environments
    }
    window.dispatchEvent(
      new CustomEvent("kene-chat-text-size-change", { detail: size }),
    );
  };

  const initials =
    `${profile.firstName.charAt(0)}${profile.lastName.charAt(0)}`.toUpperCase() ||
    "U";

  return (
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
                {initials}
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
                  <Label htmlFor="firstName">First Name</Label>
                  <Input
                    id="firstName"
                    value={profile.firstName}
                    onChange={handleProfileChange}
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input
                    id="lastName"
                    value={profile.lastName}
                    onChange={handleProfileChange}
                    className="mt-1.5"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  value={profile.email}
                  onChange={handleProfileChange}
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Your email is used for login and notifications
                </p>
              </div>

              <div>
                <Label htmlFor="jobTitle">Job Title</Label>
                <Input
                  id="jobTitle"
                  value={profile.jobTitle}
                  onChange={handleProfileChange}
                  className="mt-1.5"
                />
              </div>

              <div className="pt-4">
                <Button onClick={saveProfile}>Save Changes</Button>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="mb-4">Integration Usernames</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Connect your accounts to receive notifications across different
              platforms
            </p>
            <div className="space-y-4">
              <div>
                <Label htmlFor="slack-username">Slack Username</Label>
                <Input
                  id="slack-username"
                  placeholder="@your.name"
                  className="mt-1.5"
                  disabled
                />
                <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                  <AlertCircle className="size-3 text-[var(--color-coral)]" />
                  <span>
                    Slack must be enabled by an organization editor in
                    Organization Settings
                  </span>
                </div>
              </div>

              <div>
                <Label htmlFor="teams-username">Microsoft Teams Username</Label>
                <Input
                  id="teams-username"
                  placeholder="your.name@company.com"
                  className="mt-1.5"
                  disabled
                />
                <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                  <AlertCircle className="size-3 text-[var(--color-coral)]" />
                  <span>
                    Microsoft Teams must be enabled by an organization editor in
                    Organization Settings
                  </span>
                </div>
              </div>

              <div className="pt-4">
                <Button disabled>Save Integration Settings</Button>
              </div>
            </div>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="notifications">
        <NotificationPreferences
          onSave={() => {
            toast({
              title: "Success",
              description: "Notification preferences updated successfully!",
            });
          }}
        />
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
                <Input id="new-password" type="password" className="mt-1.5" />
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
                {
                  device: "MacBook Pro",
                  location: "San Francisco, CA",
                  lastActive: "2 minutes ago",
                  current: true,
                },
                {
                  device: "iPhone 14",
                  location: "San Francisco, CA",
                  lastActive: "1 hour ago",
                  current: false,
                },
                {
                  device: "Chrome on Windows",
                  location: "New York, NY",
                  lastActive: "2 days ago",
                  current: false,
                },
              ].map((session) => (
                <div
                  key={session.device}
                  className="flex items-center justify-between p-4 rounded-lg border-2"
                >
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium">{session.device}</p>
                      {session.current && (
                        <Badge
                          variant="secondary"
                          style={{
                            background: "var(--color-violet-500)",
                            color: "var(--color-text-inverse)",
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
            <h2 className="mb-4">Language &amp; Region</h2>
            <div className="space-y-4 max-w-md">
              <div>
                <Label htmlFor="language">Preferred Language</Label>
                <Select defaultValue="en" disabled>
                  <SelectTrigger
                    id="language"
                    className="mt-1.5 opacity-50 cursor-not-allowed"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-xs bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)] px-2 py-0.5 rounded-full">
                    Coming Soon
                  </span>
                </div>
              </div>

              <div>
                <Label htmlFor="timezone-pref">Timezone</Label>
                <Select defaultValue="america-new-york" disabled>
                  <SelectTrigger
                    id="timezone-pref"
                    className="mt-1.5 opacity-50 cursor-not-allowed"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="america-new-york">
                      Eastern Time (ET)
                    </SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-xs bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)] px-2 py-0.5 rounded-full">
                    Coming Soon
                  </span>
                </div>
              </div>

              <div>
                <Label htmlFor="date-format">Date Format</Label>
                <Select defaultValue="mm-dd-yyyy" disabled>
                  <SelectTrigger
                    id="date-format"
                    className="mt-1.5 opacity-50 cursor-not-allowed"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mm-dd-yyyy">MM/DD/YYYY</SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-xs bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)] px-2 py-0.5 rounded-full">
                    Coming Soon
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="mb-4">Interface Preferences</h2>
            <div className="space-y-4">
              <div>
                <Label htmlFor="chat-text-size">Chat Text Size</Label>
                <Select
                  value={chatTextSize}
                  onValueChange={handleChatTextSizeChange}
                >
                  <SelectTrigger
                    id="chat-text-size"
                    className="mt-1.5 max-w-md"
                  >
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
                  Adjust the size of text in chat messages for better
                  readability
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
  );
};

export default UserSettings;
