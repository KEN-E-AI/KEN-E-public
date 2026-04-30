import { useState } from "react";

const Reports = () => {
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
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Reports</h1>
      </header>
      <div className="space-y-6">
        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Reports Overview
          </h2>
          <p className="text-dashboard-gray-600">
            Access comprehensive marketing reports, schedule automated
            reporting, and export data for stakeholder presentations.
          </p>
        </div>
      </div>
    </>
  );
};

export default Reports;
