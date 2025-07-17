import { Sun, Monitor, Moon } from "lucide-react";
import { useState } from "react";

export function AppearanceSettings() {
  const [selectedMode, setSelectedMode] = useState<'light' | 'system' | 'dark'>('light');

  const colorModes = [
    {
      id: 'light' as const,
      label: 'Light',
      icon: Sun,
    },
    {
      id: 'system' as const,
      label: 'System',
      icon: Monitor,
    },
    {
      id: 'dark' as const,
      label: 'Dark',
      icon: Moon,
    },
  ];

  return (
    <div className="flex-1 bg-gray-50 p-8">
      <div className="max-w-2xl">
        <h1 className="text-2xl text-gray-900 mb-8">Appearance</h1>
        
        <div>
          <h2 className="text-sm text-gray-900 mb-2">Color mode</h2>
          <p className="text-sm text-gray-600 mb-6">
            Choose whether the Console's appearance should be light, dark, or use your computer's settings.
          </p>
          
          <div className="flex gap-4">
            {colorModes.map((mode) => {
              const Icon = mode.icon;
              const isSelected = selectedMode === mode.id;
              
              return (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`flex flex-col items-center gap-3 p-6 rounded-lg border-2 transition-colors min-w-32 ${
                    isSelected 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <Icon 
                    className={`w-5 h-5 ${
                      isSelected ? 'text-blue-600' : 'text-gray-600'
                    }`} 
                  />
                  <span 
                    className={`text-sm ${
                      isSelected ? 'text-blue-900' : 'text-gray-900'
                    }`}
                  >
                    {mode.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}