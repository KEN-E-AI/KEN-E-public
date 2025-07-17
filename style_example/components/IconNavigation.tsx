import { Home, BarChart3, Settings, Hammer, Database, Users } from "lucide-react";

interface IconNavigationProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
}

export function IconNavigation({ activeSection, onSectionChange }: IconNavigationProps) {
  const navigationItems = [
    { id: 'home', icon: Home, label: 'Home' },
    { id: 'build', icon: Hammer, label: 'Build' },
    { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'manage', icon: Database, label: 'Manage' },
    { id: 'settings', icon: Settings, label: 'Settings' }
  ];

  return (
    <div className="w-14 bg-gray-900 h-screen flex flex-col">
      {/* Logo/Brand */}
      <div className="h-14 flex items-center justify-center border-b border-gray-700">
        <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
          <span className="text-white text-xs">A</span>
        </div>
      </div>

      {/* Navigation Icons */}
      <div className="flex-1 py-4">
        <div className="space-y-1">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            
            return (
              <div key={item.id} className="relative group">
                <button
                  onClick={() => onSectionChange(item.id)}
                  className={`w-full h-12 flex items-center justify-center transition-colors ${
                    isActive 
                      ? 'bg-blue-600 text-white' 
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
                  }`}
                  title={item.label}
                >
                  <Icon className="w-5 h-5" />
                </button>
                
                {/* Tooltip */}
                <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                  {item.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}