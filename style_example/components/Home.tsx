export function Home() {
  return (
    <div className="flex-1 bg-gray-50 p-8">
      <div className="max-w-4xl">
        <h1 className="text-3xl text-gray-900 mb-2">Welcome to Anthropic Console</h1>
        <p className="text-gray-600 mb-8">
          Get started with building, analyzing, and managing your AI applications.
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg text-gray-900 mb-2">Build</h3>
            <p className="text-gray-600 text-sm">
              Create and develop your AI applications with our comprehensive tools.
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg text-gray-900 mb-2">Analytics</h3>
            <p className="text-gray-600 text-sm">
              Monitor usage, costs, and performance metrics for your applications.
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg text-gray-900 mb-2">Manage</h3>
            <p className="text-gray-600 text-sm">
              Configure API keys, limits, and organizational settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}