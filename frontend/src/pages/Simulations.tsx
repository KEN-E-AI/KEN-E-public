import { useState } from "react";
import Layout from "@/components/layout/Layout";

const Simulations = () => {
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
      pageTitle="Simulations"
      selectedTab="Simulations"
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      <div className="space-y-6">
        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Simulations Overview
          </h2>
          <p className="text-dashboard-gray-600">
            Run marketing scenario simulations, forecast outcomes, and model
            different strategic approaches to optimize future campaigns.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default Simulations;
