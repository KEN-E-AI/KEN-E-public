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
      {/*
        `MeasurementStrategyControlsProps` does not declare onEditSteps /
        funnelSteps / dateRange / setDateRange / comparisonDateRange /
        setComparisonDateRange. Those six were being passed but the component
        never consumed them — dead wires that the no-op typecheck script
        hid. They're stripped here. If/when MeasurementStrategyControls
        grows those features, re-add the passes AND the prop declarations
        in the same change.
      */}
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
        channels={currentStepData.channels}
        channelTactics={currentStepData.channelTactics}
        onChannelsChange={handleChannelsChange}
        onChannelTacticsChange={handleChannelTacticsChange}
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
