import { useState } from "react";
import { IconNavigation } from "./components/IconNavigation";
import { Sidebar } from "./components/Sidebar";
import { SettingsSidebar } from "./components/SettingsSidebar";
import { AppearanceSettings } from "./components/AppearanceSettings";
import { Home } from "./components/Home";
import { ChatWindow } from "./components/ChatWindow";

export default function App() {
  const [activeSection, setActiveSection] = useState("home");
  const [isSettingsSelected, setIsSettingsSelected] = useState(false);
  const [selectedSetting, setSelectedSetting] = useState("Appearance");

  const handleSectionChange = (section: string) => {
    setActiveSection(section);
    if (section === 'settings') {
      setIsSettingsSelected(true);
    } else {
      setIsSettingsSelected(false);
    }
  };

  const handleSettingsClick = () => {
    setIsSettingsSelected(true);
    setActiveSection('settings');
  };

  const handleSettingSelect = (setting: string) => {
    setSelectedSetting(setting);
  };

  const renderContent = () => {
    if (activeSection === 'home') {
      return <Home />;
    }

    if (activeSection === 'build') {
      return (
        <div className="flex-1 bg-gray-50 p-8">
          <div className="max-w-2xl">
            <h1 className="text-2xl text-gray-900">Build</h1>
            <p className="text-gray-600 mt-4">Build tools and applications would go here.</p>
          </div>
        </div>
      );
    }

    if (activeSection === 'analytics') {
      return (
        <div className="flex-1 bg-gray-50 p-8">
          <div className="max-w-2xl">
            <h1 className="text-2xl text-gray-900">Analytics</h1>
            <p className="text-gray-600 mt-4">Analytics dashboard would go here.</p>
          </div>
        </div>
      );
    }

    if (activeSection === 'manage' && !isSettingsSelected) {
      return (
        <div className="flex-1 bg-gray-50 p-8">
          <div className="max-w-2xl">
            <h1 className="text-2xl text-gray-900">Manage</h1>
            <p className="text-gray-600 mt-4">Management tools would go here.</p>
          </div>
        </div>
      );
    }

    if (activeSection === 'settings' || isSettingsSelected) {
      switch (selectedSetting) {
        case "Appearance":
          return <AppearanceSettings />;
        case "Profile":
          return (
            <div className="flex-1 bg-gray-50 p-8">
              <div className="max-w-2xl">
                <h1 className="text-2xl text-gray-900">Profile Settings</h1>
                <p className="text-gray-600 mt-4">Profile settings would go here.</p>
              </div>
            </div>
          );
        case "Organization":
          return (
            <div className="flex-1 bg-gray-50 p-8">
              <div className="max-w-2xl">
                <h1 className="text-2xl text-gray-900">Organization Settings</h1>
                <p className="text-gray-600 mt-4">Organization settings would go here.</p>
              </div>
            </div>
          );
        default:
          return (
            <div className="flex-1 bg-gray-50 p-8">
              <div className="max-w-2xl">
                <h1 className="text-2xl text-gray-900">{selectedSetting}</h1>
                <p className="text-gray-600 mt-4">{selectedSetting} settings would go here.</p>
              </div>
            </div>
          );
      }
    }

    return (
      <div className="flex-1 bg-gray-50 p-8">
        <div className="max-w-2xl">
          <h1 className="text-2xl text-gray-900">Select an option from the menu</h1>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <IconNavigation 
        activeSection={activeSection}
        onSectionChange={handleSectionChange}
      />
      <Sidebar 
        activeSection={activeSection}
        onSettingsClick={handleSettingsClick}
        isSettingsSelected={isSettingsSelected}
      />
      {(activeSection === 'settings' || isSettingsSelected) && (
        <SettingsSidebar 
          selectedSetting={selectedSetting}
          onSettingSelect={handleSettingSelect}
        />
      )}
      {renderContent()}
      <ChatWindow />
    </div>
  );
}