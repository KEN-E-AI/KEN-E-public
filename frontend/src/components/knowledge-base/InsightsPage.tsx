const InsightsPage = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-dashboard-gray-900">
          Insights
        </h2>
      </div>

      <div className="bg-white border border-dashboard-gray-200 rounded-lg p-8">
        <div className="text-center">
          <h3 className="text-lg font-medium text-dashboard-gray-900 mb-2">
            Insights Page
          </h3>
          <p className="text-dashboard-gray-600">
            This page will contain analytical insights and data-driven
            recommendations.
          </p>
        </div>
      </div>
    </div>
  );
};

export default InsightsPage;
