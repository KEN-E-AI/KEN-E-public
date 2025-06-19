import React, { useState } from "react";
import MeasurementStrategyControls from "./MeasurementStrategyControls";
import EditStepsModal from "./EditStepsModal";
import { useDashboardState } from "@/hooks/useDashboardState";

interface DashboardViewProps {
  selectedTab: string;
  selectedChannel: string;
  selectedTactic: string;
  dateRange: { from: Date; to: Date };
  setDateRange: (range: { from: Date; to: Date }) => void;
  comparisonDateRange?: { from: Date; to: Date };
  setComparisonDateRange?: (range: { from: Date; to: Date }) => void;
  onTabChange?: (tab: string) => void;
  onChannelChange?: (channel: string) => void;
  onTacticChange?: (tactic: string) => void;
}

const DashboardView: React.FC<DashboardViewProps> = ({
  selectedTab,
  selectedChannel,
  selectedTactic,
  dateRange,
  setDateRange,
  comparisonDateRange,
  setComparisonDateRange = () => {},
  onTabChange = () => {},
  onChannelChange = () => {},
  onTacticChange = () => {},
}) => {
  const [editStepsModalOpen, setEditStepsModalOpen] = useState(false);

  const {
    getCurrentAccountData,
    getCurrentStepData,
    handleChannelsChange,
    handleChannelTacticsChange,
    handleFunnelStepsChange,
    handleTabChange,
  } = useDashboardState();

  const currentAccountData = getCurrentAccountData();
  const currentStepData = getCurrentStepData();

  // Get funnel steps from objectives or fallback to legacy funnelSteps
  const funnelSteps =
    currentAccountData.objectives || currentAccountData.funnelSteps || [];

  return (
    <>
      {/* Dashboard Controls */}
      <MeasurementStrategyControls
        selectedChannel={selectedChannel}
        setSelectedChannel={onChannelChange}
        selectedTactic={selectedTactic}
        setSelectedTactic={onTacticChange}
        selectedTab={selectedTab}
        setSelectedTab={(tab) => {
          handleTabChange(tab);
          onTabChange(tab);
        }}
        onEditSteps={() => setEditStepsModalOpen(true)}
        funnelSteps={funnelSteps}
        channels={currentStepData.channels}
        channelTactics={currentStepData.channelTactics}
        onChannelsChange={handleChannelsChange}
        onChannelTacticsChange={handleChannelTacticsChange}
        dateRange={dateRange}
        setDateRange={setDateRange}
        comparisonDateRange={comparisonDateRange}
        setComparisonDateRange={setComparisonDateRange}
      />

      {/* Main Content Area */}

      {/* Edit Steps Modal */}
      <EditStepsModal
        open={editStepsModalOpen}
        onOpenChange={setEditStepsModalOpen}
        steps={funnelSteps}
        onStepsChange={handleFunnelStepsChange}
      />
    </>
  );
};

export default DashboardView;
