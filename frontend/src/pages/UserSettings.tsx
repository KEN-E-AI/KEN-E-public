import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ContextBreadcrumb } from "@/components/ui/context-breadcrumb";
import { User, Bell, Shield, Globe, Moon, Sun, ArrowLeft } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const UserSettings = () => {
  const navigate = useNavigate();
  const {
    user,
    notificationSettings,
    securitySettings,
    updateUser,
    setNotificationSettings,
  } = useAuth();
  const [profile, setProfile] = useState({
    firstName: user?.firstName || "",
    lastName: user?.lastName || "",
    email: user?.email || "",
    jobTitle: user?.jobTitle || "",
  });
  const [preferences, setPreferences] = useState(user?.preferences || {});
  const [localNotificationSettings, setLocalNotificationSettings] =
    useState(notificationSettings);

  if (!user) return <div>Loading...</div>;

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setProfile({ ...profile, [e.target.id]: e.target.value });
  };

  const handlePreferenceChange = (key: string, value: string) => {
    setPreferences({ ...preferences, [key]: value });
  };

  const handleNotificationChange = (id: string, enabled: boolean) => {
    setLocalNotificationSettings((prevSettings) =>
      prevSettings.map((setting) =>
        setting.id === id ? { ...setting, enabled } : setting,
      ),
    );
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
          preferences,
        },
      );

      updateUser({
        firstName: profile.firstName,
        lastName: profile.lastName,
        email: profile.email,
        jobTitle: profile.jobTitle,
        preferences,
      });

      alert("Profile saved successfully!");
    } catch (error) {
      console.error("Error saving profile:", error);
      alert("Failed to save profile.");
    }
  };

  const saveNotificationSettings = async () => {
    try {
      await Promise.all(
        localNotificationSettings.map((setting) =>
          axios.put(
            `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/users/${user.id}/notifications/${setting.id}?account_id=${user.id}`,
            { enabled: setting.enabled },
          ),
        ),
      );

      setNotificationSettings(localNotificationSettings);

      alert("Notification settings updated successfully!");
    } catch (error) {
      console.error("Error saving notification settings:", error);
      alert("Failed to save notification settings.");
    }
  };

  return (
    <Layout pageTitle="User Settings">
      <div className="max-w-4xl mx-auto space-y-8">
        <ContextBreadcrumb currentPage="user" showUserContext={true} />

        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-dashboard-gray-900">
            User Settings
          </h1>
          <p className="text-dashboard-gray-600 mt-2">
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
          <CardContent className="space-y-6">
            <div className="space-y-4">
              {localNotificationSettings.map((setting, index) => (
                <div key={setting.id}>
                  <div className="flex items-center justify-between gap-4 mb-2">
                    <div>
                      <Label>{setting.label}</Label>
                      <p className="text-sm text-dashboard-gray-600">
                        {setting.description}
                      </p>
                    </div>
                    <Switch
                      checked={setting.enabled}
                      onCheckedChange={(checked) =>
                        handleNotificationChange(setting.id, checked as boolean)
                      }
                    />
                  </div>
                  {index < localNotificationSettings.length - 1 && (
                    <Separator />
                  )}
                </div>
              ))}
              <Button onClick={saveNotificationSettings}>
                Save Notification Changes
              </Button>
            </div>
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
              <Label>Language</Label>
              <Select
                defaultValue={preferences.language || "en"}
                onValueChange={(value) =>
                  handlePreferenceChange("language", value)
                }
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Español</SelectItem>
                  <SelectItem value="fr">Français</SelectItem>
                  <SelectItem value="de">Deutsch</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <Label>Theme</Label>
              <Select
                defaultValue={preferences.theme || "light"}
                onValueChange={(value) =>
                  handlePreferenceChange("theme", value)
                }
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">
                    <Sun className="inline h-4 w-4 mr-2" />
                    Light
                  </SelectItem>
                  <SelectItem value="dark">
                    <Moon className="inline h-4 w-4 mr-2" />
                    Dark
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <Label>Date Format</Label>
              <Select
                defaultValue={preferences.date_format || "mm-dd-yyyy"}
                onValueChange={(value) =>
                  handlePreferenceChange("date_format", value)
                }
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mm-dd-yyyy">MM/DD/YYYY</SelectItem>
                  <SelectItem value="dd-mm-yyyy">DD/MM/YYYY</SelectItem>
                  <SelectItem value="yyyy-mm-dd">YYYY-MM-DD</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={saveProfile}>Save Changes</Button>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default UserSettings;
