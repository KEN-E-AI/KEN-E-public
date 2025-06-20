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
import { User, Bell, Shield, Globe, Moon, Sun } from "lucide-react";
import {
  userSettingsData,
  getUserProfile,
  getNotificationSettings,
  getSecuritySettings,
  getPreferenceSettings,
} from "@/data";

const UserSettings = () => {
  const profile = getUserProfile();
  const notificationSettings = getNotificationSettings();
  const securitySettings = getSecuritySettings();
  const preferenceSettings = getPreferenceSettings();

  return (
    <Layout pageTitle={userSettingsData.page_title}>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-dashboard-gray-900">
            {userSettingsData.header.title}
          </h1>
          <p className="text-dashboard-gray-600 mt-2">
            {userSettingsData.header.description}
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
                <Input id="firstName" defaultValue={profile.first_name} />
              </div>
              <div className="flex flex-col">
                <Label htmlFor="lastName" className="mr-auto">
                  Last Name
                </Label>
                <Input id="lastName" defaultValue={profile.last_name} />
              </div>
            </div>
            <div className="flex flex-col">
              <Label htmlFor="email" className="mr-auto">
                Email Address
              </Label>
              <Input id="email" type="email" defaultValue={profile.email} />
            </div>
            <div className="flex flex-col">
              <Label htmlFor="title" className="mr-auto">
                Job Title
              </Label>
              <Input id="title" defaultValue={profile.job_title} />
            </div>
            <Button>Save Changes</Button>
          </CardContent>
        </Card>

        {/* Notification Preferences */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Notification Preferences
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              {notificationSettings.map((setting, index) => (
                <div key={setting.id}>
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex flex-col min-w-0 flex-1">
                      <Label className="mr-auto">{setting.label}</Label>
                      <p className="text-sm text-dashboard-gray-600">
                        {setting.description}
                      </p>
                    </div>
                    <Switch
                      defaultChecked={setting.enabled}
                      className="flex-shrink-0"
                    />
                  </div>
                  {index < notificationSettings.length - 1 && <Separator />}
                </div>
              ))}
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
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex flex-col min-w-0 flex-1">
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
                    {setting.action_type === "switch" && (
                      <Switch
                        defaultChecked={setting.enabled}
                        className="flex-shrink-0"
                      />
                    )}
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
            <div className="space-y-4">
              {preferenceSettings.map((setting, index) => (
                <div key={setting.id}>
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex flex-col min-w-0 flex-1">
                      <Label className="mr-auto">{setting.label}</Label>
                      <p className="text-sm text-dashboard-gray-600">
                        {setting.description}
                      </p>
                    </div>
                    <Select defaultValue={setting.value}>
                      <SelectTrigger className="w-[150px] flex-shrink-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {setting.options.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.icon ? (
                              <div className="flex items-center gap-2">
                                {option.icon === "sun" && (
                                  <Sun className="h-4 w-4" />
                                )}
                                {option.icon === "moon" && (
                                  <Moon className="h-4 w-4" />
                                )}
                                {option.label}
                              </div>
                            ) : (
                              option.label
                            )}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {index < preferenceSettings.length - 1 && <Separator />}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default UserSettings;
