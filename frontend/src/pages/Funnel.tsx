import { useState } from "react";
import Layout from "@/components/layout/Layout";

const Funnel = () => {
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);

  return (
    <Layout
      pageTitle="Funnel"
      selectedTab="Funnel"
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      <div className="space-y-6">
        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Funnel Overview
          </h2>
          <p className="text-dashboard-gray-600">
            Analyze your marketing funnel, track conversion rates, and identify
            optimization opportunities across each stage of the customer
            journey.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default Funnel;
