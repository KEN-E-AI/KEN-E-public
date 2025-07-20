import { useState, useEffect } from "react";
import { Edit2 } from "lucide-react";
import EditChannelsModal from "./EditChannelsModal";
import EditTacticsModal from "./EditTacticsModal";
import ChannelControls from "./ChannelControls";
import { cn } from "@/lib/utils";

interface Channel {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface Tactic {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface MeasurementStrategyControlsProps {
  selectedChannel: string;
  setSelectedChannel: (channel: string) => void;
  selectedTactic: string;
  setSelectedTactic: (tactic: string) => void;
  selectedTab?: string;
  setSelectedTab?: (tab: string) => void;
  channels?: Channel[];
  channelTactics?: Record<string, Tactic[]>;
  onChannelsChange?: (channels: Channel[]) => void;
  onChannelTacticsChange?: (channelName: string, tactics: Tactic[]) => void;
}

const MeasurementStrategyControls = ({
  selectedChannel,
  setSelectedChannel,
  selectedTactic,
  setSelectedTactic,
  selectedTab = "Awareness",
  setSelectedTab = () => {},
  channels = [],
  channelTactics = {},
  onChannelsChange = () => {},
  onChannelTacticsChange = () => {},
}: MeasurementStrategyControlsProps) => {
  const [editChannelsModalOpen, setEditChannelsModalOpen] = useState(false);
  const [editTacticsModalOpen, setEditTacticsModalOpen] = useState(false);
  const [localChannels, setLocalChannels] = useState<Channel[]>(channels);
  const [allChannelTactics, setAllChannelTactics] =
    useState<Record<string, Tactic[]>>(channelTactics);

  // Sync props with local state
  useEffect(() => {
    setLocalChannels(channels);
  }, [channels]);

  useEffect(() => {
    setAllChannelTactics(channelTactics);
  }, [channelTactics]);

  // Auto-select "Overview" tactic when channel changes
  useEffect(() => {
    if (selectedChannel !== "Overview") {
      const tactics = allChannelTactics[selectedChannel] || [];
      // Check if current tactic is valid for this channel (Overview is always valid)
      const currentTacticValid =
        selectedTactic === "Overview" ||
        tactics.some((tactic) => tactic.name === selectedTactic);

      if (!currentTacticValid) {
        // Current tactic is invalid, select Overview by default
        setSelectedTactic("Overview");
      }
    } else {
      // Overview channel selected, clear tactic
      setSelectedTactic("");
    }
  }, [selectedChannel, allChannelTactics, setSelectedTactic]);

  // Get tactics for the currently selected channel
  const currentTactics = allChannelTactics[selectedChannel] || [];

  // Update tactics for a specific channel
  const updateChannelTactics = (channelName: string, tactics: Tactic[]) => {
    const updatedTactics = {
      ...allChannelTactics,
      [channelName]: tactics,
    };
    setAllChannelTactics(updatedTactics);
    onChannelTacticsChange(channelName, tactics);
  };

  // Handle channel changes
  const handleChannelsChange = (newChannels: Channel[]) => {
    setLocalChannels(newChannels);
    onChannelsChange(newChannels);
  };

  return (
    <>
      <div className="rounded-lg bg-white border border-dashboard-gray-200 my-6">
        <div className="flex flex-col rounded-xl overflow-hidden h-screen mb-6">
          {/* React Flow Channel Controls */}
          <div className="mt-6">
            <ChannelControls />
          </div>
        </div>

        {/* Edit Channels Modal */}
        <EditChannelsModal
          open={editChannelsModalOpen}
          onOpenChange={setEditChannelsModalOpen}
          channels={localChannels}
          onChannelsChange={handleChannelsChange}
        />

        {/* Edit Tactics Modal */}
        <EditTacticsModal
          open={editTacticsModalOpen}
          onOpenChange={setEditTacticsModalOpen}
          tactics={currentTactics}
          onTacticsChange={(newTactics) =>
            updateChannelTactics(selectedChannel, newTactics)
          }
        />
      </div>
    </>
  );
};

export default MeasurementStrategyControls;
