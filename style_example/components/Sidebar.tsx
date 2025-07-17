import { ChevronDown } from "lucide-react";

interface SidebarProps {
  activeSection: string;
  onSettingsClick: () => void;
  isSettingsSelected: boolean;
}

export function Sidebar({ activeSection, onSettingsClick, isSettingsSelected }: SidebarProps) {
  const buildItems = [
    "Dashboard",
    "Workbench", 
    "Files"
  ];

  const analyticsItems = [
    "Usage",
    "Cost",
    "Logs",
    "Batches",
    "Claude Code"
  ];

  const manageItems = [
    "API keys",
    "Limits",
    "Settings"
  ];

  // Don't render if not in a relevant section
  if (!['build', 'analytics', 'manage', 'settings'].includes(activeSection)) {
    return null;
  }

  return (
    <div className="w-64 bg-white border-r border-gray-200 h-screen flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h1 className="text-lg text-black">ANTHROPIC</h1>
          <ChevronDown className="w-4 h-4 text-gray-400" />
        </div>
        <div className="mt-2 flex items-center gap-2">
          <div className="w-6 h-6 bg-gray-100 rounded border border-gray-200 flex items-center justify-center">
            <span className="text-xs text-gray-600">Org</span>
          </div>
          <div>
            <div className="text-sm text-gray-900">Organization</div>
            <div className="text-xs text-gray-500">FCR-E LIG</div>
          </div>
          <ChevronDown className="w-3 h-3 text-gray-400 ml-auto" />
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto">
        {/* BUILD Section */}
        {activeSection === 'build' && (
          <div className="p-4">
            <div className="text-xs text-gray-500 mb-2">BUILD</div>
            <div className="space-y-1">
              {buildItems.map((item) => (
                <div key={item} className="text-sm text-gray-700 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                  {item}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ANALYTICS Section */}
        {activeSection === 'analytics' && (
          <div className="p-4">
            <div className="text-xs text-gray-500 mb-2">ANALYTICS</div>
            <div className="space-y-1">
              {analyticsItems.map((item) => (
                <div key={item} className="text-sm text-gray-700 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                  {item}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MANAGE Section */}
        {activeSection === 'manage' && (
          <div className="p-4">
            <div className="text-xs text-gray-500 mb-2">MANAGE</div>
            <div className="space-y-1">
              {manageItems.map((item) => (
                <div 
                  key={item} 
                  className={`text-sm py-1 px-2 hover:bg-gray-50 rounded cursor-pointer ${
                    item === 'Settings' && isSettingsSelected ? 'text-gray-900 bg-gray-50' : 'text-gray-700'
                  }`}
                  onClick={item === 'Settings' ? onSettingsClick : undefined}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Settings Section - show all items when in settings */}
        {activeSection === 'settings' && (
          <>
            <div className="p-4">
              <div className="text-xs text-gray-500 mb-2">BUILD</div>
              <div className="space-y-1">
                {buildItems.map((item) => (
                  <div key={item} className="text-sm text-gray-700 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="px-4 pb-4">
              <div className="text-xs text-gray-500 mb-2">ANALYTICS</div>
              <div className="space-y-1">
                {analyticsItems.map((item) => (
                  <div key={item} className="text-sm text-gray-700 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="px-4 pb-4">
              <div className="text-xs text-gray-500 mb-2">MANAGE</div>
              <div className="space-y-1">
                {manageItems.map((item) => (
                  <div 
                    key={item} 
                    className={`text-sm py-1 px-2 hover:bg-gray-50 rounded cursor-pointer ${
                      item === 'Settings' && isSettingsSelected ? 'text-gray-900 bg-gray-50' : 'text-gray-700'
                    }`}
                    onClick={item === 'Settings' ? onSettingsClick : undefined}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}