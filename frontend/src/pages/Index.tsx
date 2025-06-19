import { useState } from "react";
import Layout from "@/components/layout/Layout";
import DashboardView from "@/components/dashboard/DashboardView";

const Index = () => {
  const [selectedAccount, setSelectedAccount] = useState("acme-corp");
  const [selectedChannel, setSelectedChannel] = useState("Overview");
  const [selectedTactic, setSelectedTactic] = useState("");
  const [selectedTab, setSelectedTab] = useState("Awareness");
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
      pageTitle="Measurement Strategy"
      selectedTab={selectedTab}
      selectedChannel={selectedChannel}
      selectedTactic={selectedTactic}
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      <DashboardView
        selectedTab={selectedTab}
        selectedChannel={selectedChannel}
        selectedTactic={selectedTactic}
        dateRange={dateRange}
        setDateRange={setDateRange}
        comparisonDateRange={comparisonDateRange}
        setComparisonDateRange={setComparisonDateRange}
        onTabChange={setSelectedTab}
        onChannelChange={setSelectedChannel}
        onTacticChange={setSelectedTactic}
      />
    </Layout>
  );
};

export default Index;
