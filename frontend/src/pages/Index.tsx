import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardView from "@/components/dashboard/DashboardView";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

const Index = () => {
  const navigate = useNavigate();
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
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Marketing Strategies</h1>
      </header>
      {/* Back to Knowledge Base Link */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/knowledge")}
          className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal mr-auto"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Knowledge Base
        </Button>
      </div>

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
    </>
  );
};

export default Index;
