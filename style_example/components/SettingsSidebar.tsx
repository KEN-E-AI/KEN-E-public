interface SettingsSidebarProps {
  selectedSetting: string;
  onSettingSelect: (setting: string) => void;
}

export function SettingsSidebar({ selectedSetting, onSettingSelect }: SettingsSidebarProps) {
  const settingsItems = [
    "Profile",
    "Appearance",
    "Organization",
    "Members",
    "Workspaces",
    "Billing",
    "Limits",
    "API keys",
    "Admin keys",
    "Privacy controls"
  ];

  return (
    <div className="w-64 bg-white border-r border-gray-200 h-screen flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <div className="space-y-1">
            {settingsItems.map((item) => (
              <div 
                key={item} 
                className={`text-sm py-1 px-2 hover:bg-gray-50 rounded cursor-pointer ${
                  item === selectedSetting ? 'text-gray-900 bg-gray-50' : 'text-gray-700'
                }`}
                onClick={() => onSettingSelect(item)}
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}