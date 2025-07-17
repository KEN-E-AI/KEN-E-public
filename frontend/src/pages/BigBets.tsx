import { useState } from "react";
import Layout from "@/components/layout/Layout";

const BigBets = () => {
  const [selectedTab, setSelectedTab] = useState("Awareness");
  const [selectedChannel, setSelectedChannel] = useState("Overview");
  const [selectedTactic, setSelectedTactic] = useState("");
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
      pageTitle="Big Bets"
      selectedTab={selectedTab}
      selectedChannel={selectedChannel}
      selectedTactic={selectedTactic}
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      {/* Big Bets page content */}
      <div className="space-y-6">
        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Big Bets Overview
          </h2>
          <p className="text-dashboard-gray-600 mb-6">
            Track and analyze your organization's biggest strategic initiatives
            and their impact on key metrics.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-gradient-to-br from-brand-light-blue/20 to-brand-light-blue/30 rounded-lg p-4 border border-brand-light-blue/40">
              <h3 className="font-semibold text-brand-dark-blue mb-2">
                Digital Transformation
              </h3>
              <p className="text-sm text-brand-dark-blue mb-3">
                Complete migration to cloud-based infrastructure
              </p>
              <div className="flex justify-between items-center">
                <span className="text-xs text-brand-medium-blue bg-brand-light-blue/40 px-2 py-1 rounded">
                  Q2 2025
                </span>
                <span className="text-lg font-bold text-brand-dark-blue">
                  65%
                </span>
              </div>
            </div>

            <div className="bg-gradient-to-br from-brand-light-green/20 to-brand-light-green/30 rounded-lg p-4 border border-brand-light-green/40">
              <h3 className="font-semibold text-brand-light-green mb-2">
                Market Expansion
              </h3>
              <p className="text-sm text-brand-light-green mb-3">
                Launch in 3 new international markets
              </p>
              <div className="flex justify-between items-center">
                <span className="text-xs text-brand-dark-blue bg-brand-light-green/40 px-2 py-1 rounded">
                  Q3 2025
                </span>
                <span className="text-lg font-bold text-brand-light-green">
                  42%
                </span>
              </div>
            </div>

            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
              <h3 className="font-semibold text-purple-900 mb-2">
                Product Innovation
              </h3>
              <p className="text-sm text-purple-700 mb-3">
                Develop AI-powered customer insights platform
              </p>
              <div className="flex justify-between items-center">
                <span className="text-xs text-purple-600 bg-purple-200 px-2 py-1 rounded">
                  Q4 2025
                </span>
                <span className="text-lg font-bold text-purple-900">28%</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Investment Allocation
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-dashboard-gray-800 mb-3">
                Budget Distribution
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-dashboard-gray-600">
                    Digital Transformation
                  </span>
                  <span className="text-sm font-medium">$2.4M</span>
                </div>
                <div className="w-full bg-dashboard-gray-200 rounded-full h-2">
                  <div
                    className="bg-brand-medium-blue h-2 rounded-full"
                    style={{ width: "45%" }}
                  ></div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm text-dashboard-gray-600">
                    Market Expansion
                  </span>
                  <span className="text-sm font-medium">$1.8M</span>
                </div>
                <div className="w-full bg-dashboard-gray-200 rounded-full h-2">
                  <div
                    className="bg-brand-light-green h-2 rounded-full"
                    style={{ width: "34%" }}
                  ></div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm text-dashboard-gray-600">
                    Product Innovation
                  </span>
                  <span className="text-sm font-medium">$1.1M</span>
                </div>
                <div className="w-full bg-dashboard-gray-200 rounded-full h-2">
                  <div
                    className="bg-purple-500 h-2 rounded-full"
                    style={{ width: "21%" }}
                  ></div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-dashboard-gray-800 mb-3">
                Key Metrics Impact
              </h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center p-3 bg-dashboard-gray-50 rounded-lg">
                  <span className="text-sm text-dashboard-gray-600">
                    Revenue Growth
                  </span>
                  <span className="text-sm font-medium text-brand-light-green">
                    +12.5%
                  </span>
                </div>
                <div className="flex justify-between items-center p-3 bg-dashboard-gray-50 rounded-lg">
                  <span className="text-sm text-dashboard-gray-600">
                    Market Share
                  </span>
                  <span className="text-sm font-medium text-brand-medium-blue">
                    +3.2%
                  </span>
                </div>
                <div className="flex justify-between items-center p-3 bg-dashboard-gray-50 rounded-lg">
                  <span className="text-sm text-dashboard-gray-600">
                    Customer Satisfaction
                  </span>
                  <span className="text-sm font-medium text-purple-600">
                    +8.1%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 border border-dashboard-gray-200">
          <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-4">
            Timeline & Milestones
          </h2>
          <p className="text-dashboard-gray-600">
            Detailed timeline view and milestone tracking for all big bets
            initiatives will be displayed here.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default BigBets;
