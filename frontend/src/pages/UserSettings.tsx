import { useState } from "react";
import axios from "axios";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { User, Bell, Shield, Globe } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { NotificationPreferences } from "@/components/notifications/NotificationPreferences";

const UserSettings = () => {
  const { toast } = useToast();
  const { user, securitySettings, updateUser } = useAuth();
  const [profile, setProfile] = useState({
    firstName: user?.firstName || "",
    lastName: user?.lastName || "",
    email: user?.email || "",
    jobTitle: user?.jobTitle || "",
  });

  if (!user) return <div>Loading...</div>;

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setProfile({ ...profile, [e.target.id]: e.target.value });
  };

  const saveProfile = async () => {
    try {
      await axios.put(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/users/${user.id}?account_id=${user.id}`,
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

      toast({
        title: "Success",
        description: "Profile saved successfully!",
      });
    } catch (error) {
      console.error("Error saving profile:", error);
      toast({
        title: "Error",
        description: "Failed to save profile.",
        variant: "destructive",
      });
    }
  };

  return (
    <SettingsLayout
      pageTitle="User Settings"
      currentPage="user"
      showEntitySelector={false}
    >
      {/* Header Description */}
      <div>
        <p className="text-dashboard-gray-600">
          Manage your personal preferences and user settings
        </p>
      </div>

      {/* Profile Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex flex-col">
              <Label htmlFor="firstName" className="mr-auto">
                First Name
              </Label>
              <Input
                id="firstName"
                value={profile.firstName}
                onChange={handleProfileChange}
              />
            </div>
            <div className="flex flex-col">
              <Label htmlFor="lastName" className="mr-auto">
                Last Name
              </Label>
              <Input
                id="lastName"
                value={profile.lastName}
                onChange={handleProfileChange}
              />
            </div>
          </div>
          <div className="flex flex-col">
            <Label htmlFor="email" className="mr-auto">
              Email Address
            </Label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={handleProfileChange}
            />
          </div>
          <div className="flex flex-col">
            <Label htmlFor="jobTitle" className="mr-auto">
              Job Title
            </Label>
            <Input
              id="jobTitle"
              value={profile.jobTitle}
              onChange={handleProfileChange}
            />
          </div>
          <Button onClick={saveProfile}>Save Changes</Button>
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" /> Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent>
          <NotificationPreferences
            onSave={() => {
              toast({
                title: "Success",
                description: "Notification preferences updated successfully!",
              });
            }}
          />
        </CardContent>
      </Card>

      {/* Security Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Security Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            {securitySettings.map((setting, index) => (
              <div key={setting.id}>
                <div className="flex items-center justify-between flex-wrap gap-4 mb-2">
                  <div className="flex flex-col min-w-0 flex-1 justify-center items-start">
                    <Label className="mr-auto">{setting.label}</Label>
                    <p className="text-sm text-dashboard-gray-600">
                      {setting.description}
                    </p>
                  </div>
                  {setting.action_type === "button" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-shrink-0"
                    >
                      {setting.action_text}
                    </Button>
                  )}
                  {/* {setting.action_type === "switch" && (
                      <Switch
                        defaultChecked={setting.enabled}
                        className="flex-shrink-0"
                      />
                    )} */}
                </div>
                {index < securitySettings.length - 1 && <Separator />}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            User Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label className="text-gray-500">Language</Label>
              <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
                Coming Soon
              </span>
            </div>
            <Select defaultValue="en" disabled={true}>
              <SelectTrigger className="w-[150px] opacity-50 cursor-not-allowed">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </SettingsLayout>
  );
};

export default UserSettings;
