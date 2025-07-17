import { useCallback, useState } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  NodeTypes,
  ReactFlowProvider,
  Handle,
  Position,
} from "reactflow";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  Edit2,
  Trash2,
  Eye,
  Calendar as CalendarIcon,
  Share2,
  Mail,
  MessageSquare,
} from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import EditObjectivesModal from "./EditObjectivesModal";
import EditChannelsModal from "./EditChannelsModal";
import EditTacticsModal from "./EditTacticsModal";
import "reactflow/dist/style.css";

// Helper function to get blue color for all nodes
const getRandomColor = () => {
  return {
    bg: "bg-brand-medium-blue",
    border: "border-brand-dark-blue",
    text: "text-white",
  };
};

interface ContextMenuProps {
  id: string;
  top: number;
  left: number;
  nodeType: string;
  nodeId: string;
  onClose: () => void;
  onView: (nodeType: string, nodeId: string) => void;
  onEdit: (nodeType: string, nodeId: string) => void;
}

const ContextMenu = ({
  id,
  top,
  left,
  nodeType,
  nodeId,
  onClose,
  onView,
  onEdit,
}: ContextMenuProps) => {
  const handleView = () => {
    console.log(`View ${nodeType}:`, nodeId);
    onView(nodeType, nodeId);
    onClose();
  };

  const handleEdit = () => {
    console.log(`Edit ${nodeType}:`, nodeId);
    onEdit(nodeType, nodeId);
    onClose();
  };

  const handleRemove = () => {
    console.log(`Remove ${nodeType}:`, nodeId);
    onClose();
  };

  const handleAddChild = () => {
    console.log(`Add child to ${nodeType}:`, nodeId);
    onClose();
  };

  // Tactic nodes are at the bottom of the hierarchy, so they can't have children
  const showAddChild = nodeType !== "tactic";

  // Get the appropriate text for the add child button based on node type
  const getAddChildText = () => {
    if (nodeType === "objective") return "Add Channel";
    if (nodeType === "channel") return "Add Tactic";
    return "Add Child"; // fallback
  };

  return (
    <div
      id={id}
      style={{ top, left }}
      className="absolute z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-1 min-w-[120px]"
    >
      <button
        onClick={handleView}
        className="w-full px-3 py-2 text-xs text-left bg-black text-white rounded hover:bg-gray-800 transition-colors mb-1"
      >
        View
      </button>
      <button
        onClick={handleEdit}
        className="w-full px-3 py-2 text-xs text-left bg-black text-white rounded hover:bg-gray-800 transition-colors mb-1"
      >
        Edit
      </button>
      <button
        onClick={handleRemove}
        className={`w-full px-3 py-2 text-xs text-left bg-black text-white rounded hover:bg-gray-800 transition-colors ${showAddChild ? "mb-1" : ""}`}
      >
        Remove
      </button>
      {showAddChild && (
        <button
          onClick={handleAddChild}
          className="w-full px-3 py-2 text-xs text-left bg-black text-white rounded hover:bg-gray-800 transition-colors"
        >
          {getAddChildText()}
        </button>
      )}
    </div>
  );
};

// Objective Node - Rectangle Shape
const ObjectiveNode = ({ data }: { data: any }) => {
  const isSelected = data.isSelected;
  const color = data.color || getRandomColor();

  const handleAddChannel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onAddChannel && data.stepId) {
      data.onAddChannel(data.stepId);
    }
  };

  const handleEditObjective = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onEdit && data.stepId) {
      data.onEdit("objective", data.stepId);
    }
  };

  const handleDeleteObjective = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onDelete && data.stepId) {
      data.onDelete("objective", data.stepId);
    }
  };

  const handleViewObjective = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onView && data.stepId) {
      data.onView("objective", data.stepId);
    }
  };

  return (
    <div
      className={`rounded-lg shadow-lg border-2 min-w-[180px] text-center cursor-pointer transition-colors text-white relative ${
        isSelected
          ? `${color.bg} ${color.border} opacity-80`
          : `${color.bg} ${color.border} ${color.hover}`
      }`}
      style={{
        width: "212px",
        minHeight: "140px",
        padding: "8px 8px 16px 9px",
      }}
    >
      <div className="font-semibold text-sm">{data.label}</div>
      <div className="text-xs my-1 mb-5 pb-2 opacity-90 whitespace-normal break-words leading-relaxed">
        Objective: {data.objective}
      </div>

      {/* Action Buttons */}
      <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1 mb-2">
        <button
          onClick={handleViewObjective}
          className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
          title="View Objective"
        >
          <Eye className="w-3 h-3 text-white" />
        </button>

        <button
          onClick={handleAddChannel}
          className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
          title="Add Channel"
        >
          <Plus className="w-3 h-3 text-white" />
        </button>
      </div>

      {/* Handle for outgoing edge (bottom) - Objectives have 1 edge */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        style={{
          background: "#6b7280",
          border: "2px solid #ffffff",
          width: "12px",
          height: "12px",
        }}
      />
    </div>
  );
};

// Channel Node - Rectangle Shape
const ChannelNode = ({ data }: { data: any }) => {
  const isSelected = data.isSelected;
  const color = data.color || getRandomColor();

  const handleAddTactic = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onAddTactic && data.objectiveId && data.channelId) {
      data.onAddTactic(data.objectiveId, data.channelId);
    }
  };

  const handleEditChannel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onEdit && data.channelId) {
      data.onEdit("channel", `${data.objectiveId}-${data.channelId}`);
    }
  };

  const handleDeleteChannel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onDelete && data.channelId) {
      data.onDelete("channel", `${data.objectiveId}-${data.channelId}`);
    }
  };

  const handleViewChannel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onView && data.channelId) {
      data.onView("channel", `${data.objectiveId}-${data.channelId}`);
    }
  };

  return (
    <div
      className={`px-6 py-4 rounded-lg shadow-lg border-2 min-w-[140px] text-center cursor-pointer transition-colors text-white relative ${
        isSelected
          ? `${color.bg} ${color.border} opacity-80`
          : `${color.bg} ${color.border} ${color.hover}`
      }`}
      style={{ minWidth: "140px", minHeight: "82px" }}
    >
      <div className="font-semibold text-sm">{data.label}</div>
      <div className="text-xs my-1 mb-5 pb-2 opacity-90">Channel</div>

      {/* Action Buttons */}
      <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1 my-2">
        <button
          onClick={handleViewChannel}
          className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
          title="View Channel"
        >
          <Eye className="w-3 h-3 text-white" />
        </button>

        <button
          onClick={handleAddTactic}
          className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
          title="Add Tactic"
        >
          <Plus className="w-3 h-3 text-white" />
        </button>
      </div>

      {/* Handle for incoming edge (top) - Channels have 2 edges */}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        style={{
          background: "#6b7280",
          border: "2px solid #ffffff",
          width: "12px",
          height: "12px",
        }}
      />

      {/* Handle for outgoing edge (bottom) - Channels have 2 edges */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        style={{
          background: "#6b7280",
          border: "2px solid #ffffff",
          width: "12px",
          height: "12px",
        }}
      />
    </div>
  );
};

// Tactic Node - Rectangle Shape
const TacticNode = ({ data }: { data: any }) => {
  const color = data.color || getRandomColor();

  const handleEditTactic = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onEdit && data.tacticKey) {
      data.onEdit(
        "tactic",
        `${data.stepId}-${data.channelKey}-${data.tacticKey}`,
      );
    }
  };

  const handleDeleteTactic = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onDelete && data.tacticKey) {
      data.onDelete(
        "tactic",
        `${data.stepId}-${data.channelKey}-${data.tacticKey}`,
      );
    }
  };

  const handleViewTactic = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onView && data.tacticKey) {
      data.onView(
        "tactic",
        `${data.stepId}-${data.channelKey}-${data.tacticKey}`,
      );
    }
  };

  return (
    <div
      className={`px-4 py-3 rounded-lg shadow-md border-2 min-w-[120px] text-center cursor-pointer transition-colors text-white relative ${color.bg} ${color.border} ${color.hover}`}
      style={{ minWidth: "120px", minHeight: "72px" }}
    >
      <div className="font-medium text-sm">{data.label}</div>
      <div className="text-xs my-1 mb-5 opacity-90">Tactic</div>

      {/* Action Buttons */}
      <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1">
        <button
          onClick={handleViewTactic}
          className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
          title="View Tactic"
        >
          <Eye className="w-3 h-3 text-white" />
        </button>
      </div>

      {/* Handle for incoming edge (top) - Tactics have 1 edge */}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        style={{
          background: "#6b7280",
          border: "2px solid #ffffff",
          width: "12px",
          height: "12px",
        }}
      />
    </div>
  );
};

// Custom node types
const nodeTypes: NodeTypes = {
  objective: ObjectiveNode,
  channel: ChannelNode,
  tactic: TacticNode,
};

interface ChannelControlsProps {
  data?: any;
}

// Main React Flow component
const ReactFlowComponent = () => {
  const [selectedObjective, setSelectedObjective] = useState<string | null>(
    null,
  );
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [menu, setMenu] = useState<{
    id: string;
    top: number;
    left: number;
    nodeType: string;
    nodeId: string;
  } | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState<{
    title: string;
    content: string;
    effectivenessKPI?: string;
    efficiencyKPI?: string;
    nodeType?: string;
    supportingMetrics?: string[];
  }>({ title: "", content: "" });

  // Edit Objectives Modal state
  const [editObjectivesModalOpen, setEditObjectivesModalOpen] = useState(false);
  const [openDirectlyToForm, setOpenDirectlyToForm] = useState(false);
  const [editObjectiveId, setEditObjectiveId] = useState<string | null>(null);

  // Edit Channels Modal state
  const [editChannelsModalOpen, setEditChannelsModalOpen] = useState(false);
  const [currentObjectiveForChannel, setCurrentObjectiveForChannel] = useState<
    string | null
  >(null);
  const [editChannelId, setEditChannelId] = useState<string | null>(null);
  const [
    currentChannelForTacticInObjectives,
    setCurrentChannelForTacticInObjectives,
  ] = useState<{
    objectiveId: string;
    channelId: string;
  } | null>(null);
  // State for editing tactics using EditChannelsModal
  const [editingTacticViaChannelsModal, setEditingTacticViaChannelsModal] =
    useState<{
      objectiveId: string;
      channelId: string;
    } | null>(null);
  const [editTacticIdViaChannelsModal, setEditTacticIdViaChannelsModal] =
    useState<string | null>(null);
  // Edit Tactics Modal state
  const [editTacticsModalOpen, setEditTacticsModalOpen] = useState(false);
  const [currentChannelForTactic, setCurrentChannelForTactic] = useState<{
    objectiveId: string;
    channelId: string;
  } | null>(null);
  const [editTacticId, setEditTacticId] = useState<string | null>(null);

  // Delete confirmation state
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [nodeToDelete, setNodeToDelete] = useState<{
    nodeType: string;
    nodeId: string;
  } | null>(null);

  // Date range state
  const [pendingDateRange, setPendingDateRange] = useState<{
    from: Date;
    to: Date;
  }>({
    from: new Date(new Date().getFullYear(), 0, 1), // January 1st of current year
    to: new Date(new Date().getFullYear(), 0, 31), // January 31st of current year
  });
  const [pendingComparisonDateRange, setPendingComparisonDateRange] = useState<{
    from: Date;
    to: Date;
  } | null>(null);

  // Sample data structure - now as state
  const [sampleData, setSampleData] = useState({
    "1": {
      step_name: "awareness",
      objective:
        "Increase the number of prospective customers who are aware of the brand and its unique positioning in the market.",
      effectivenessKPI: "Brand Awareness Lift",
      efficiencyKPI: "Cost Per Impression",
      supportingMetrics: ["Reach", "Frequency", "Video Completion Rate"],
      channels: {
        display: { tactics: { banner_ads: {}, video_ads: {} } },
        social: { tactics: { organic_posts: {}, boosted_posts: {} } },
        search: { tactics: { sem: {}, seo: {} } },
        email: { tactics: { newsletter: {}, followup: {} } },
      },
    },
    "2": {
      step_name: "consideration",
      objective:
        "Ensure that customers currently in the market for air purifiers are evaluating products on intellipure.com.",
      effectivenessKPI: "Sessions",
      efficiencyKPI: "Cost Per Click",
      supportingMetrics: [
        "Page Views",
        "Bounce Rate",
        "Average Session Duration",
      ],
      channels: {
        social: { tactics: { organic_posts: {}, boosted_posts: {} } },
        email: { tactics: { newsletter: {}, followup: {} } },
      },
    },
    "3": {
      step_name: "conversion",
      objective:
        "Persuade customers visiting intellipure.com to purchase a new unit.",
      effectivenessKPI: "Conversion Rate",
      efficiencyKPI: "Cost Per Acquisition",
      supportingMetrics: [
        "Add to Cart Events",
        "Checkout Events",
        "Average Order Value",
      ],
      channels: {
        social: { tactics: { organic_posts: {}, boosted_posts: {} } },
        email: { tactics: { newsletter: {}, followup: {} } },
      },
    },
    "4": {
      step_name: "loyalty",
      objective:
        "Ensure that existing customers continue to purchase filter refills.",
      effectivenessKPI: "Customer Lifetime Value",
      efficiencyKPI: "Cost Per Retained Client",
      supportingMetrics: [
        "Retention Rate",
        "Repeat Purchase Rate",
        "Email Open Rate",
      ],
      channels: {
        social: { tactics: { organic_posts: {}, boosted_posts: {} } },
        email: { tactics: { newsletter: {}, followup: {} } },
      },
    },
  });

  // Handle view modal
  const handleViewModal = (nodeType: string, nodeId: string) => {
    if (nodeType === "objective") {
      // Find the objective data
      const objectiveKey = nodeId;
      const objectiveData = sampleData[objectiveKey as keyof typeof sampleData];

      if (objectiveData) {
        setModalContent({
          title: `${objectiveData.step_name.charAt(0).toUpperCase() + objectiveData.step_name.slice(1)} Objective`,
          content: objectiveData.objective,
          effectivenessKPI: objectiveData.effectivenessKPI,
          efficiencyKPI: objectiveData.efficiencyKPI,
          nodeType: "Objective",
          supportingMetrics: objectiveData.supportingMetrics,
          id: objectiveKey,
        });
      }
    } else if (nodeType === "channel") {
      // For channels, extract objective and channel data
      const [objectiveId, channelId] = nodeId.split("-");
      const objectiveData = sampleData[objectiveId as keyof typeof sampleData];
      const channelData = objectiveData?.channels[channelId];

      setModalContent({
        title: `${channelId.charAt(0).toUpperCase() + channelId.slice(1)} Channel`,
        effectivenessKPI:
          channelData?.effectivenessKPI || objectiveData?.effectivenessKPI,
        efficiencyKPI:
          channelData?.efficiencyKPI || objectiveData?.efficiencyKPI,
        nodeType: "Channel",
        supportingMetrics:
          channelData?.supportingMetrics || objectiveData?.supportingMetrics,
        id: channelId,
        objectiveId: objectiveId,
      });
    } else if (nodeType === "tactic") {
      // For tactics, extract objective, channel, and tactic data
      const [objectiveId, channelId, tacticId] = nodeId.split("-");
      const objectiveData = sampleData[objectiveId as keyof typeof sampleData];
      const channelData = objectiveData?.channels[channelId];
      const tacticData = channelData?.tactics?.[tacticId];

      setModalContent({
        title: `${tacticId.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())} Tactic`,
        effectivenessKPI:
          tacticData?.effectivenessKPI ||
          channelData?.effectivenessKPI ||
          objectiveData?.effectivenessKPI,
        efficiencyKPI:
          tacticData?.efficiencyKPI ||
          channelData?.efficiencyKPI ||
          objectiveData?.efficiencyKPI,
        nodeType: "Tactic",
        supportingMetrics:
          tacticData?.supportingMetrics ||
          channelData?.supportingMetrics ||
          objectiveData?.supportingMetrics,
        id: tacticId,
        objectiveId: objectiveId,
        channelId: channelId,
      });
    }
    setModalOpen(true);
  };

  // Handle edit modal
  const handleEditModal = (nodeType: string, nodeId: string) => {
    if (nodeType === "objective") {
      // Set the objective ID to edit and open the modal
      setEditObjectiveId(nodeId);
      setOpenDirectlyToForm(false);
      setEditObjectivesModalOpen(true);
    } else {
      // For channels and tactics, just log for now
      console.log(`Edit ${nodeType}:`, nodeId);
    }
  };

  // Handle begin analysis button click
  const handleBeginAnalysis = () => {
    console.log("Begin Analysis clicked");
    setModalOpen(false);
  };

  // Handle add channel button click
  const handleAddChannel = (objectiveId: string) => {
    console.log("Add channel for objective:", objectiveId);
    setCurrentObjectiveForChannel(objectiveId);
    setOpenDirectlyToForm(true);
    setEditObjectivesModalOpen(true);
  };

  // Handle add tactic button click
  const handleAddTactic = (objectiveId: string, channelId: string) => {
    console.log(
      "Add tactic for channel:",
      channelId,
      "in objective:",
      objectiveId,
    );
    setCurrentChannelForTacticInObjectives({ objectiveId, channelId });
    setOpenDirectlyToForm(true);
    setEditObjectivesModalOpen(true);
  };

  // Handle delete for objectives, channels, and tactics
  const handleDeleteNode = (nodeType: string, nodeId: string) => {
    console.log(`Delete ${nodeType}:`, nodeId);

    if (nodeType === "objective") {
      const updatedData = { ...sampleData };
      delete updatedData[nodeId];
      setSampleData(updatedData);
    } else if (nodeType === "channel") {
      const [objectiveId, channelId] = nodeId.split("-");
      const updatedData = { ...sampleData };
      if (updatedData[objectiveId] && updatedData[objectiveId].channels) {
        delete updatedData[objectiveId].channels[channelId];
      }
      setSampleData(updatedData);
    } else if (nodeType === "tactic") {
      const [objectiveId, channelId, tacticId] = nodeId.split("-");
      const updatedData = { ...sampleData };
      if (
        updatedData[objectiveId] &&
        updatedData[objectiveId].channels[channelId] &&
        updatedData[objectiveId].channels[channelId].tactics
      ) {
        delete updatedData[objectiveId].channels[channelId].tactics[tacticId];
      }
      setSampleData(updatedData);
    }
  };

  // Helper function to get channels for current objective
  const getCurrentChannels = () => {
    if (
      !currentObjectiveForChannel ||
      !sampleData[currentObjectiveForChannel]
    ) {
      return [];
    }
    const objective = sampleData[currentObjectiveForChannel];
    return Object.entries(objective.channels).map(([id, channel]) => ({
      id,
      name: channel?.name || id.charAt(0).toUpperCase() + id.slice(1),
      effectivenessKPI: channel?.effectivenessKPI || "",
      efficiencyKPI: channel?.efficiencyKPI || "",
      supportingMetrics: channel?.supportingMetrics || [],
      ...channel,
    }));
  };

  // Helper function to get tactics for current channel
  const getCurrentTactics = () => {
    if (
      !currentChannelForTactic ||
      !sampleData[currentChannelForTactic.objectiveId]
    ) {
      return [];
    }
    const objective = sampleData[currentChannelForTactic.objectiveId];
    const channel = objective.channels[currentChannelForTactic.channelId];
    if (!channel || !channel.tactics) {
      return [];
    }
    return Object.entries(channel.tactics).map(([id, tactic]) => ({
      id,
      name:
        tactic?.name ||
        id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, " "),
      effectivenessKPI: tactic?.effectivenessKPI || "",
      efficiencyKPI: tactic?.efficiencyKPI || "",
      supportingMetrics: tactic?.supportingMetrics || [],
      ...tactic,
    }));
  };

  // Helper function to get tactics for EditChannelsModal format
  const getTacticsForChannelsModal = () => {
    if (
      !editingTacticViaChannelsModal ||
      !sampleData[editingTacticViaChannelsModal.objectiveId]
    ) {
      return [];
    }
    const objective = sampleData[editingTacticViaChannelsModal.objectiveId];
    const channel = objective.channels[editingTacticViaChannelsModal.channelId];
    if (!channel || !channel.tactics) {
      return [];
    }
    return Object.entries(channel.tactics).map(([id, tactic]) => ({
      id,
      name:
        tactic?.name ||
        id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, " "),
      effectivenessKPI: tactic?.effectivenessKPI || "",
      efficiencyKPI: tactic?.efficiencyKPI || "",
      supportingMetrics: tactic?.supportingMetrics || [],
    }));
  };

  // Handle channels change
  const handleChannelsChange = (channels: any[]) => {
    if (!currentObjectiveForChannel) return;

    const updatedData = { ...sampleData };
    const newChannels: Record<string, any> = {};

    channels.forEach((channel) => {
      newChannels[channel.id] = {
        name: channel.name,
        effectivenessKPI: channel.effectivenessKPI,
        efficiencyKPI: channel.efficiencyKPI,
        supportingMetrics: channel.supportingMetrics,
        tactics:
          sampleData[currentObjectiveForChannel]?.channels[channel.id]
            ?.tactics || {},
      };
    });

    updatedData[currentObjectiveForChannel] = {
      ...updatedData[currentObjectiveForChannel],
      channels: newChannels,
    };

    setSampleData(updatedData);
  };

  // Handle tactics change via EditChannelsModal
  const handleTacticsChangeViaChannelsModal = (tactics: any[]) => {
    if (!editingTacticViaChannelsModal) return;

    const updatedData = { ...sampleData };
    const newTactics: Record<string, any> = {};

    tactics.forEach((tactic) => {
      newTactics[tactic.id] = {
        name: tactic.name,
        effectivenessKPI: tactic.effectivenessKPI,
        efficiencyKPI: tactic.efficiencyKPI,
        supportingMetrics: tactic.supportingMetrics,
      };
    });

    if (
      !updatedData[editingTacticViaChannelsModal.objectiveId].channels[
        editingTacticViaChannelsModal.channelId
      ]
    ) {
      updatedData[editingTacticViaChannelsModal.objectiveId].channels[
        editingTacticViaChannelsModal.channelId
      ] = { tactics: {} };
    }

    updatedData[editingTacticViaChannelsModal.objectiveId].channels[
      editingTacticViaChannelsModal.channelId
    ].tactics = newTactics;

    setSampleData(updatedData);
  };

  // Handle tactics change
  const handleTacticsChange = (tactics: any[]) => {
    if (!currentChannelForTactic) return;

    const updatedData = { ...sampleData };
    const newTactics: Record<string, any> = {};

    tactics.forEach((tactic) => {
      newTactics[tactic.id] = {
        name: tactic.name,
        effectivenessKPI: tactic.effectivenessKPI,
        efficiencyKPI: tactic.efficiencyKPI,
        supportingMetrics: tactic.supportingMetrics,
      };
    });

    if (
      !updatedData[currentChannelForTactic.objectiveId].channels[
        currentChannelForTactic.channelId
      ]
    ) {
      updatedData[currentChannelForTactic.objectiveId].channels[
        currentChannelForTactic.channelId
      ] = { tactics: {} };
    }

    updatedData[currentChannelForTactic.objectiveId].channels[
      currentChannelForTactic.channelId
    ].tactics = newTactics;

    setSampleData(updatedData);
  };

  // Generate nodes and edges
  const generateNodesAndEdges = () => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Always show objective nodes
    const objectiveKeys = Object.keys(sampleData);
    const objectiveSpacing = 236;
    const startX = 20; // Start with 20px padding from left edge
    const startY = 72; // Start with 72px padding from top edge

    objectiveKeys.forEach((key, index) => {
      const objective = sampleData[key as keyof typeof sampleData];
      const objectiveId = `objective-${key}`;
      const isSelected = selectedObjective === key;

      nodes.push({
        id: objectiveId,
        type: "objective",
        position: { x: startX + index * objectiveSpacing, y: startY },
        data: {
          label:
            objective.step_name.charAt(0).toUpperCase() +
            objective.step_name.slice(1),
          objective: objective.objective,
          stepId: key,
          isSelected,
          color: getRandomColor(),
          onAddChannel: handleAddChannel,
          onEdit: handleEditModal,
          onDelete: handleDeleteNode,
          onView: handleViewModal,
        },
        draggable: false,
      });

      // If this objective is selected, show its channels
      if (selectedObjective === key) {
        const channelKeys = Object.keys(objective.channels);
        const channelSpacing = 180;
        const channelStartX = (-(channelKeys.length - 1) * channelSpacing) / 2;
        const baseChannelX = startX + index * objectiveSpacing;

        channelKeys.forEach((channelKey, channelIndex) => {
          const channelId = `channel-${key}-${channelKey}`;
          const channelIsSelected = selectedChannel === `${key}-${channelKey}`;
          const channelData = objective.channels[channelKey];
          const channelDisplayName =
            channelData?.name ||
            channelKey.charAt(0).toUpperCase() + channelKey.slice(1);

          nodes.push({
            id: channelId,
            type: "channel",
            position: {
              x: baseChannelX + channelStartX + channelIndex * channelSpacing,
              y: 308,
            },
            data: {
              label: channelDisplayName,
              channelKey: channelKey,
              channelId: channelKey,
              objectiveId: key,
              stepId: key,
              isSelected: channelIsSelected,
              color: getRandomColor(),
              onAddTactic: handleAddTactic,
              onEdit: handleEditModal,
              onDelete: handleDeleteNode,
              onView: handleViewModal,
            },
            draggable: false,
          });

          // Add edge from objective to channel
          edges.push({
            id: `edge-${objectiveId}-${channelId}`,
            source: objectiveId,
            target: channelId,
            type: "smoothstep",
            style: { stroke: "#6b7280", strokeWidth: 2 },
            sourceHandle: "bottom",
            targetHandle: "top",
          });

          // If this channel is selected, show its tactics
          if (selectedChannel === `${key}-${channelKey}`) {
            const channel =
              objective.channels[channelKey as keyof typeof objective.channels];
            const tacticKeys = Object.keys(channel.tactics || {});
            const tacticSpacing = 140;
            const tacticStartX = (-(tacticKeys.length - 1) * tacticSpacing) / 2;

            tacticKeys.forEach((tacticKey, tacticIndex) => {
              const tacticId = `tactic-${key}-${channelKey}-${tacticKey}`;
              const tacticData = channel.tactics?.[tacticKey];
              const tacticDisplayName =
                tacticData?.name ||
                tacticKey
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase());

              nodes.push({
                id: tacticId,
                type: "tactic",
                position: {
                  x:
                    baseChannelX +
                    channelStartX +
                    channelIndex * channelSpacing +
                    tacticStartX +
                    tacticIndex * tacticSpacing,
                  y: 486,
                },
                data: {
                  label: tacticDisplayName,
                  tacticKey: tacticKey,
                  channelKey: channelKey,
                  stepId: key,
                  color: getRandomColor(),
                  onEdit: handleEditModal,
                  onDelete: handleDeleteNode,
                  onView: handleViewModal,
                },
                draggable: false,
              });

              // Add edge from channel to tactic
              edges.push({
                id: `edge-${channelId}-${tacticId}`,
                source: channelId,
                target: tacticId,
                type: "smoothstep",
                style: { stroke: "#6b7280", strokeWidth: 2 },
                sourceHandle: "bottom",
                targetHandle: "top",
              });
            });
          }
        });
      }
    });

    return { nodes, edges };
  };

  const { nodes, edges } = generateNodesAndEdges();

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    console.log("Node clicked:", node.data.label);

    if (node.type === "objective") {
      setSelectedObjective((prev) =>
        prev === node.data.stepId ? null : node.data.stepId,
      );
      setSelectedChannel(null);
    } else if (node.type === "channel") {
      const channelKey = `${node.data.stepId}-${node.data.channelKey}`;
      setSelectedChannel((prev) => (prev === channelKey ? null : channelKey));
    }
  }, []);

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      // Prevent native context menu from showing
      event.preventDefault();

      // Get node ID based on node type
      let nodeId = "";
      if (node.type === "objective") {
        nodeId = node.data.stepId;
      } else if (node.type === "channel") {
        nodeId = `${node.data.stepId}-${node.data.channelKey}`;
      } else if (node.type === "tactic") {
        nodeId = `${node.data.stepId}-${node.data.channelKey}-${node.data.tacticKey}`;
      }

      // Calculate position for context menu
      const pane = document.querySelector(".react-flow__pane") as HTMLElement;
      const rect = pane?.getBoundingClientRect();

      setMenu({
        id: node.id,
        top: event.clientY - (rect?.top || 0),
        left: event.clientX - (rect?.left || 0),
        nodeType: node.type || "unknown",
        nodeId: nodeId,
      });
    },
    [],
  );

  const onPaneClick = useCallback(() => {
    setMenu(null);
  }, []);

  return (
    <div className="h-full w-full relative">
      {/* Controls Container - Responsive Layout */}
      <div className="absolute top-4 left-4 right-4 z-10">
        {/* Large screen layout - side by side */}
        <div className="hidden lg:flex justify-between items-start">
          {/* Add Objective Button - Large screens */}
          <Button
            onClick={() => {
              setOpenDirectlyToForm(true);
              setEditObjectivesModalOpen(true);
            }}
            className="bg-black text-white hover:bg-gray-800"
          >
            Add Objective
          </Button>
        </div>

        {/* Small/Medium screen layout - stacked */}
        <div className="lg:hidden">
          <div className="flex flex-col gap-3">
            {/* Date Range Pickers Row */}
            <div className="flex gap-2 flex-wrap">
              {/* Primary Date Range */}
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className={cn(
                      "justify-start text-left font-normal",
                      !pendingDateRange && "text-muted-foreground",
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {pendingDateRange?.from ? (
                      pendingDateRange.to ? (
                        <>
                          {format(pendingDateRange.from, "LLL dd, y")} -{" "}
                          {format(pendingDateRange.to, "LLL dd, y")}
                        </>
                      ) : (
                        format(pendingDateRange.from, "LLL dd, y")
                      )
                    ) : (
                      <span>Pick a date</span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <div className="p-3 border-b">
                    <h4 className="font-medium text-sm text-gray-900 mb-2">
                      Primary Date Range
                    </h4>
                    <Calendar
                      mode="range"
                      defaultMonth={pendingDateRange?.from}
                      selected={pendingDateRange}
                      onSelect={(range) => range && setPendingDateRange(range)}
                      numberOfMonths={2}
                    />
                  </div>
                </PopoverContent>
              </Popover>

              {/* Comparison Date Range */}
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className={cn(
                      "justify-start text-left font-normal text-gray-600",
                      !pendingComparisonDateRange && "text-muted-foreground",
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {pendingComparisonDateRange?.from ? (
                      pendingComparisonDateRange.to ? (
                        <>
                          {format(pendingComparisonDateRange.from, "LLL dd, y")}{" "}
                          - {format(pendingComparisonDateRange.to, "LLL dd, y")}
                        </>
                      ) : (
                        format(pendingComparisonDateRange.from, "LLL dd, y")
                      )
                    ) : (
                      <span>Compare to...</span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <div className="p-3">
                    <h4 className="font-medium text-sm text-gray-900 mb-2">
                      Comparison Date Range
                    </h4>
                    <Calendar
                      mode="range"
                      defaultMonth={pendingComparisonDateRange?.from}
                      selected={pendingComparisonDateRange}
                      onSelect={(range) => setPendingComparisonDateRange(range)}
                      numberOfMonths={2}
                    />
                  </div>
                </PopoverContent>
              </Popover>
            </div>

            {/* Add Objective Button - Small/Medium screens */}
            <div className="flex justify-end">
              <Button
                onClick={() => {
                  setOpenDirectlyToForm(true);
                  setEditObjectivesModalOpen(true);
                }}
                className="bg-black text-white hover:bg-gray-800"
              >
                Add Objective
              </Button>
            </div>
          </div>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={onNodeClick}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        fitView={false}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
        elementsSelectable={true}
        nodesConnectable={false}
        nodesDraggable={false}
        panOnDrag={true}
        zoomOnScroll={true}
        zoomOnPinch={true}
        preventScrolling={false}
      >
        <Controls />
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#e2e8f0"
        />
      </ReactFlow>

      {menu && (
        <ContextMenu
          {...menu}
          onClose={() => setMenu(null)}
          onView={handleViewModal}
          onEdit={handleEditModal}
        />
      )}

      {/* View Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogTitle className="sr-only">{modalContent.title}</DialogTitle>
          <div className="text-lg font-normal tracking-tight leading-tight">
            {modalContent.title}
          </div>
          {modalContent.content && (
            <div className="text-sm text-gray-600 mt-2">
              {modalContent.content}
            </div>
          )}

          {/* Divider */}
          {modalContent.content &&
            (modalContent.effectivenessKPI || modalContent.efficiencyKPI) && (
              <div className="border-t border-gray-200"></div>
            )}

          {/* KPI Information */}
          {(modalContent.effectivenessKPI || modalContent.efficiencyKPI) && (
            <div className="mt-6 space-y-8">
              {modalContent.effectivenessKPI && (
                <div>
                  {/* Header with status dot */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-3 h-3 bg-brand-light-green rounded-full"></div>
                    <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                      EFFECTIVENESS
                    </h3>
                  </div>

                  {/* Metric info */}
                  <div className="mb-3">
                    <h4 className="font-semibold text-gray-900 mb-1">
                      {modalContent.effectivenessKPI}
                    </h4>
                    <p className="text-sm text-gray-600 mb-4">
                      The estimated portion of impressions served to new
                      prospects across platforms, channels, websites and apps.
                    </p>
                  </div>

                  {/* Scorecard and Chart Container */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
                    {/* Scorecard */}
                    <div className="md:col-span-1 bg-gray-50 overflow-hidden flex flex-col justify-center items-center">
                      <div className="text-4xl font-bold text-gray-900 mb-2 text-center">
                        1,529,204
                      </div>
                      <div className="text-brand-light-green font-medium text-center">
                        +20%
                      </div>
                    </div>
                    {/* Line Chart */}
                    <div className="md:col-span-2">
                      <div className="h-32 relative">
                        <svg
                          viewBox="0 0 300 120"
                          className="w-full h-full flex flex-col justify-center items-center"
                        >
                          {/* Y-axis labels */}
                          <text x="10" y="15" className="text-xs fill-gray-400">
                            $50,000
                          </text>
                          <text x="10" y="65" className="text-xs fill-gray-400">
                            $25,000
                          </text>
                          <text
                            x="10"
                            y="115"
                            className="text-xs fill-gray-400"
                          >
                            $0
                          </text>

                          {/* Chart line */}
                          <polyline
                            fill="none"
                            stroke="#374151"
                            strokeWidth="2"
                            points="50,100 80,95 110,90 140,85 170,75 200,60 230,45 260,30"
                            className="ml-2"
                          />

                          {/* X-axis labels */}
                          <text
                            x="50"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Jan
                          </text>
                          <text
                            x="80"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Feb
                          </text>
                          <text
                            x="110"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Mar
                          </text>
                          <text
                            x="140"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Apr
                          </text>
                          <text
                            x="170"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            May
                          </text>
                          <text
                            x="200"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Jun
                          </text>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Divider */}
              {modalContent.effectivenessKPI && modalContent.efficiencyKPI && (
                <div className="border-t border-gray-200"></div>
              )}

              {modalContent.efficiencyKPI && (
                <div className="mt-4">
                  {/* Header with status dot */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-3 h-3 bg-brand-yellow rounded-full"></div>
                    <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                      EFFICIENCY
                    </h3>
                  </div>

                  {/* Metric info */}
                  <div className="mb-3">
                    <h4 className="font-semibold text-gray-900 mb-1">
                      {modalContent.efficiencyKPI}
                    </h4>
                    <p className="text-sm text-gray-600 mb-4">
                      The average cost paid for each impression served to
                      prospects across all advertising channels and platforms.
                    </p>
                  </div>

                  {/* Scorecard and Chart Container */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Scorecard */}
                    <div className="md:col-span-1 bg-gray-50 rounded-lg overflow-hidden flex flex-col justify-center items-center">
                      <div className="text-4xl font-bold text-gray-900 mb-2 text-center">
                        $2.47
                      </div>
                      <div className="text-brand-yellow font-medium text-center">
                        -5%
                      </div>
                    </div>

                    {/* Line Chart */}
                    <div className="md:col-span-2">
                      <div className="h-32 relative">
                        <svg
                          viewBox="0 0 300 120"
                          className="w-full h-full flex flex-col justify-center items-center"
                        >
                          {/* Y-axis labels */}
                          <text x="10" y="15" className="text-xs fill-gray-400">
                            $4.00
                          </text>
                          <text x="10" y="65" className="text-xs fill-gray-400">
                            $2.00
                          </text>
                          <text
                            x="10"
                            y="115"
                            className="text-xs fill-gray-400"
                          >
                            $0
                          </text>

                          {/* Chart line */}
                          <polyline
                            fill="none"
                            stroke="#374151"
                            strokeWidth="2"
                            points="50,40 80,45 110,50 140,55 170,60 200,58 230,52 260,45"
                            className="ml-2"
                          />

                          {/* X-axis labels */}
                          <text
                            x="50"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Jan
                          </text>
                          <text
                            x="80"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Feb
                          </text>
                          <text
                            x="110"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Mar
                          </text>
                          <text
                            x="140"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Apr
                          </text>
                          <text
                            x="170"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            May
                          </text>
                          <text
                            x="200"
                            y="135"
                            className="text-xs fill-gray-400"
                          >
                            Jun
                          </text>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Divider */}
          {(modalContent.effectivenessKPI || modalContent.efficiencyKPI) &&
            modalContent.supportingMetrics &&
            modalContent.supportingMetrics.length > 0 && (
              <div className="border-t border-gray-200"></div>
            )}

          {/* Supporting Metrics */}
          {modalContent.supportingMetrics &&
            modalContent.supportingMetrics.length > 0 && (
              <div className="mt-8">
                <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide mb-6">
                  SUPPORTING METRICS
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {modalContent.supportingMetrics.map((metric, index) => {
                    // Generate sample data for each metric
                    const sampleValues = [
                      { value: "847,392", change: "+15%", trend: "positive" },
                      { value: "2.3%", change: "-8%", trend: "negative" },
                      { value: "4:32", change: "+12%", trend: "positive" },
                      { value: "64.7%", change: "+3%", trend: "positive" },
                      { value: "$47.23", change: "-2%", trend: "negative" },
                      { value: "23,401", change: "+25%", trend: "positive" },
                    ];
                    const sampleData =
                      sampleValues[index % sampleValues.length];
                    const changeColor =
                      sampleData.trend === "positive"
                        ? "text-brand-light-green"
                        : "text-red-600";

                    return (
                      <div key={metric} className="bg-gray-50 p-4 rounded-lg">
                        <h4 className="font-medium text-sm text-gray-900 mb-2">
                          {metric}
                        </h4>
                        <div className="text-2xl font-bold text-gray-900 mb-1">
                          {sampleData.value}
                        </div>
                        <div className={`${changeColor} font-medium text-sm`}>
                          {sampleData.change}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          <div className="flex justify-end mt-6 gap-3">
            {/* Share Button with Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="flex items-center gap-2">
                  <Share2 className="w-4 h-4" />
                  Share
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => {
                    // Handle share by email
                    console.log("Share by Email clicked");
                    // TODO: Implement email sharing functionality
                  }}
                  className="flex items-center gap-2"
                >
                  <Mail className="w-4 h-4" />
                  Share by Email
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    // Handle share on Slack
                    console.log("Share on Slack clicked");
                    // TODO: Implement Slack sharing functionality
                  }}
                  className="flex items-center gap-2"
                >
                  <MessageSquare className="w-4 h-4" />
                  Share on Slack
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="outline"
              onClick={() => {
                // Close the current modal first
                setModalOpen(false);

                // Determine which modal to open based on the node type
                if (modalContent.nodeType === "Objective") {
                  // For objectives, open the edit objectives modal with the specific objective
                  setEditObjectiveId(modalContent.id);
                  setOpenDirectlyToForm(true);
                  setEditObjectivesModalOpen(true);
                } else if (modalContent.nodeType === "Channel") {
                  // For channels, open the edit channels modal
                  setCurrentObjectiveForChannel(modalContent.objectiveId);
                  setEditChannelId(modalContent.id);
                  setEditChannelsModalOpen(true);
                } else if (modalContent.nodeType === "Tactic") {
                  // For tactics, use EditChannelsModal (reused for tactics)
                  setEditingTacticViaChannelsModal({
                    objectiveId: modalContent.objectiveId,
                    channelId: modalContent.channelId,
                  });
                  setEditTacticIdViaChannelsModal(modalContent.id);
                  setEditChannelsModalOpen(true);
                }
              }}
              className="flex items-center gap-2"
            >
              <Edit2 className="w-4 h-4" />
              Edit
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                // Prepare node information for deletion
                let nodeType = "";
                let nodeId = "";

                if (modalContent.nodeType === "Objective") {
                  nodeType = "objective";
                  nodeId = modalContent.id;
                } else if (modalContent.nodeType === "Channel") {
                  nodeType = "channel";
                  nodeId = `${modalContent.objectiveId}-${modalContent.id}`;
                } else if (modalContent.nodeType === "Tactic") {
                  nodeType = "tactic";
                  nodeId = `${modalContent.objectiveId}-${modalContent.channelId}-${modalContent.id}`;
                }

                // Set the node to delete and show confirmation dialog
                setNodeToDelete({ nodeType, nodeId });
                setDeleteConfirmOpen(true);
              }}
              className="flex items-center gap-2 text-red-600 hover:text-red-700 border-red-300 hover:border-red-400"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </Button>
            <Button
              onClick={handleBeginAnalysis}
              className="bg-black text-white hover:bg-gray-800"
            >
              Analyze {modalContent.nodeType || "Tree"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Objectives Modal */}
      <EditObjectivesModal
        open={editObjectivesModalOpen}
        onOpenChange={(open) => {
          setEditObjectivesModalOpen(open);
          if (!open) {
            setOpenDirectlyToForm(false);
            setEditObjectiveId(null);
            setCurrentObjectiveForChannel(null);
            setCurrentChannelForTacticInObjectives(null);
          }
        }}
        sampleData={sampleData}
        onSampleDataChange={setSampleData}
        openDirectlyToForm={openDirectlyToForm}
        editObjectiveId={editObjectiveId || undefined}
        showReturnToView={openDirectlyToForm && Boolean(editObjectiveId)}
        entityType={
          currentObjectiveForChannel
            ? "channel"
            : currentChannelForTacticInObjectives
              ? "tactic"
              : "objective"
        }
        parentObjectiveId={
          currentObjectiveForChannel ||
          currentChannelForTacticInObjectives?.objectiveId ||
          undefined
        }
        parentChannelId={
          currentChannelForTacticInObjectives?.channelId || undefined
        }
        onReturnToView={() => {
          // Close edit modal and reopen view modal with the same content
          setEditObjectivesModalOpen(false);
          setOpenDirectlyToForm(false);
          setEditObjectiveId(null);
          setCurrentObjectiveForChannel(null);
          setCurrentChannelForTacticInObjectives(null);
          // Reopen view modal with the previous content
          setModalOpen(true);
        }}
      />

      {/* Edit Channels Modal (also used for Tactics) */}
      <EditChannelsModal
        open={editChannelsModalOpen}
        onOpenChange={(open) => {
          setEditChannelsModalOpen(open);
          if (!open) {
            setCurrentObjectiveForChannel(null);
            setEditChannelId(null);
            setEditingTacticViaChannelsModal(null);
            setEditTacticIdViaChannelsModal(null);
          }
        }}
        channels={
          editingTacticViaChannelsModal
            ? getTacticsForChannelsModal()
            : getCurrentChannels()
        }
        onChannelsChange={
          editingTacticViaChannelsModal
            ? handleTacticsChangeViaChannelsModal
            : handleChannelsChange
        }
        showReturnToView={Boolean(
          editChannelId || editTacticIdViaChannelsModal,
        )}
        editChannelId={
          editChannelId || editTacticIdViaChannelsModal || undefined
        }
        entityType={editingTacticViaChannelsModal ? "tactic" : "channel"}
        onReturnToView={() => {
          // Close edit modal
          setEditChannelsModalOpen(false);

          // Refresh modal content with updated data if editing a tactic
          if (editingTacticViaChannelsModal && editTacticIdViaChannelsModal) {
            const { objectiveId, channelId } = editingTacticViaChannelsModal;
            const tacticId = editTacticIdViaChannelsModal;

            // Get fresh tactic data
            const objectiveData =
              sampleData[objectiveId as keyof typeof sampleData];
            const channelData = objectiveData?.channels[channelId];
            const tacticData = channelData?.tactics?.[tacticId];

            // Update modal content with fresh data
            setModalContent({
              title: `${tacticId.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())} Tactic`,
              effectivenessKPI:
                tacticData?.effectivenessKPI ||
                channelData?.effectivenessKPI ||
                objectiveData?.effectivenessKPI,
              efficiencyKPI:
                tacticData?.efficiencyKPI ||
                channelData?.efficiencyKPI ||
                objectiveData?.efficiencyKPI,
              nodeType: "Tactic",
              supportingMetrics:
                tacticData?.supportingMetrics ||
                channelData?.supportingMetrics ||
                objectiveData?.supportingMetrics,
              id: tacticId,
              objectiveId: objectiveId,
              channelId: channelId,
            });
          }

          // Clear states
          setCurrentObjectiveForChannel(null);
          setEditChannelId(null);
          setEditingTacticViaChannelsModal(null);
          setEditTacticIdViaChannelsModal(null);

          // Reopen view modal
          setModalOpen(true);
        }}
      />

      {/* Edit Tactics Modal */}
      <EditTacticsModal
        open={editTacticsModalOpen}
        onOpenChange={(open) => {
          setEditTacticsModalOpen(open);
          if (!open) {
            setCurrentChannelForTactic(null);
            setEditTacticId(null);
          }
        }}
        tactics={getCurrentTactics()}
        onTacticsChange={handleTacticsChange}
        showReturnToView={Boolean(editTacticId)}
        editTacticId={editTacticId || undefined}
        onReturnToView={() => {
          // Close edit modal and reopen view modal
          setEditTacticsModalOpen(false);
          setCurrentChannelForTactic(null);
          setEditTacticId(null);
          // Reopen view modal
          setModalOpen(true);
        }}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Deletion</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this node along with any child
              nodes?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteConfirmOpen(false)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                // Close confirmation dialog
                setDeleteConfirmOpen(false);

                // Close view modal
                setModalOpen(false);

                // Perform the deletion
                if (nodeToDelete) {
                  handleDeleteNode(nodeToDelete.nodeType, nodeToDelete.nodeId);
                  setNodeToDelete(null);
                }
              }}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const ChannelControls = ({ data: propData }: ChannelControlsProps) => {
  console.log("ChannelControls component rendering with React Flow...");

  return (
    <div className="w-full h-[641px] bg-white overflow-hidden">
      <div className="text-sm text-gray-600 border-b border-gray-200 px-4 pb-4 flex justify-between items-center">
        <span>
          Use the diagram below to define what you business wants to accomplish
          and how you will know when you are successful. Click 'Help' to have
          KEN-E do it for you.
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            // Handle help functionality
            console.log("Help button clicked");
            // TODO: Implement help dialog or redirect to help documentation
          }}
          className="ml-4 flex-shrink-0"
        >
          Help
        </Button>
      </div>
      <div className="h-[calc(100%-100px)] w-full relative flex flex-col flex-grow">
        <ReactFlowProvider>
          <ReactFlowComponent />
        </ReactFlowProvider>
      </div>
    </div>
  );
};

export default ChannelControls;
