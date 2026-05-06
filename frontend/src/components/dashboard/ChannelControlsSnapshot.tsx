import React, { useState, useCallback } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  NodeTypes,
  ReactFlowProvider,
  Handle,
  Position,
} from "reactflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Eye,
  BarChart3,
  Plus,
  Edit2,
  Trash2,
  Share2,
  Mail,
  MessageSquare,
} from "lucide-react";
import "reactflow/dist/style.css";

// Static snapshot data - frozen at time of report generation
const snapshotData = {
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
};

// Helper function to get color (matches original ChannelControls.tsx)
const getRandomColor = () => {
  const colors = [
    { bg: "bg-red-500", border: "border-red-600", hover: "hover:bg-red-600" },
    {
      bg: "bg-brand-yellow",
      border: "border-brand-yellow",
      hover: "hover:bg-brand-yellow/90",
    },
    {
      bg: "bg-brand-dark-green",
      border: "border-brand-dark-green",
      hover: "hover:bg-brand-dark-green/90",
    },
  ];
  return colors[Math.floor(Math.random() * colors.length)];
};

// Custom Node Components (matching original ChannelControls.tsx styling)
const ObjectiveNode = ({ data }: { data: any }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const color = data.color || getRandomColor();

  return (
    <>
      <div
        className={`rounded-lg shadow-lg border-2 min-w-[180px] text-center cursor-pointer transition-colors text-white relative ${color.bg} ${color.border} ${color.hover}`}
        style={{
          width: "212px",
          minHeight: "140px",
          padding: "8px 8px 16px 9px",
        }}
      >
        <div className="flex items-start justify-center mb-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide">
            {data.step_name}
          </h3>
        </div>
        <p className="text-xs leading-tight">{data.objective}</p>

        {/* Action Buttons */}
        <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1 my-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setModalOpen(true);
            }}
            className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
            title="View Objective"
          >
            <Eye className="w-3 h-3 text-white" />
          </button>
        </div>

        {/* Expansion Indicator */}
        <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-1/2">
          <div className="w-6 h-6 bg-white border-2 border-[var(--color-border-default)] rounded-full flex items-center justify-center shadow-sm">
            {data.isSelected ? (
              <span className="text-xs font-bold text-[var(--color-text-tertiary)]">
                -
              </span>
            ) : (
              <span className="text-xs font-bold text-[var(--color-text-tertiary)]">
                +
              </span>
            )}
          </div>
        </div>

        {/* Handle for outgoing edge (bottom) */}
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

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="capitalize">
              {data.step_name} Objective
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            <p className="text-[var(--color-text-secondary)]">
              {data.objective}
            </p>

            {/* Divider */}
            {(data.effectivenessKPI || data.efficiencyKPI) && (
              <div className="border-t border-[var(--color-border-default)]"></div>
            )}

            <div className="mt-6 space-y-8">
              {data.effectivenessKPI && (
                <div>
                  {/* Header with status dot */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-3 h-3 bg-brand-light-green rounded-full"></div>
                    <h3 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">
                      EFFECTIVENESS
                    </h3>
                  </div>

                  {/* Metric info */}
                  <div className="mb-3">
                    <h4 className="font-semibold text-[var(--color-text-primary)] mb-1">
                      {data.effectivenessKPI}
                    </h4>
                    <p className="text-sm text-[var(--color-text-tertiary)] mb-4">
                      The estimated portion of impressions served to new
                      prospects across platforms, channels, websites and apps.
                    </p>
                  </div>

                  {/* Scorecard and Chart Container */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
                    {/* Scorecard */}
                    <div className="md:col-span-1 bg-[var(--color-bg-secondary)] overflow-hidden flex flex-col justify-center items-center py-6">
                      <div className="text-4xl font-bold text-[var(--color-text-primary)] mb-2 text-center">
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
                          <text
                            x="10"
                            y="15"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            2.0M
                          </text>
                          <text
                            x="10"
                            y="65"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            1.0M
                          </text>
                          <text
                            x="10"
                            y="115"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            0
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
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Jan
                          </text>
                          <text
                            x="80"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Feb
                          </text>
                          <text
                            x="110"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Mar
                          </text>
                          <text
                            x="140"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Apr
                          </text>
                          <text
                            x="170"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            May
                          </text>
                          <text
                            x="200"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
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
              {data.effectivenessKPI && data.efficiencyKPI && (
                <div className="border-t border-[var(--color-border-default)]"></div>
              )}

              {data.efficiencyKPI && (
                <div className="mt-4">
                  {/* Header with status dot */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-3 h-3 bg-brand-yellow rounded-full"></div>
                    <h3 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">
                      EFFICIENCY
                    </h3>
                  </div>

                  {/* Metric info */}
                  <div className="mb-3">
                    <h4 className="font-semibold text-[var(--color-text-primary)] mb-1">
                      {data.efficiencyKPI}
                    </h4>
                    <p className="text-sm text-[var(--color-text-tertiary)] mb-4">
                      The average cost paid for each impression served to
                      prospects across all advertising channels and platforms.
                    </p>
                  </div>

                  {/* Scorecard and Chart Container */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Scorecard */}
                    <div className="md:col-span-1 bg-[var(--color-bg-secondary)] rounded-lg overflow-hidden flex flex-col justify-center items-center py-6">
                      <div className="text-4xl font-bold text-[var(--color-text-primary)] mb-2 text-center">
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
                          <text
                            x="10"
                            y="15"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            $4.00
                          </text>
                          <text
                            x="10"
                            y="65"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            $2.00
                          </text>
                          <text
                            x="10"
                            y="115"
                            className="text-xs fill-[var(--color-text-tertiary)]"
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
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Jan
                          </text>
                          <text
                            x="80"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Feb
                          </text>
                          <text
                            x="110"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Mar
                          </text>
                          <text
                            x="140"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            Apr
                          </text>
                          <text
                            x="170"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
                          >
                            May
                          </text>
                          <text
                            x="200"
                            y="135"
                            className="text-xs fill-[var(--color-text-tertiary)]"
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

            {/* Divider */}
            {(data.effectivenessKPI || data.efficiencyKPI) &&
              data.supportingMetrics &&
              data.supportingMetrics.length > 0 && (
                <div className="border-t border-[var(--color-border-default)]"></div>
              )}

            {/* Supporting Metrics */}
            {data.supportingMetrics && data.supportingMetrics.length > 0 && (
              <div className="mt-8">
                <h3 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide mb-6">
                  SUPPORTING METRICS
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {data.supportingMetrics.map((metric, index) => {
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
                      <div
                        key={metric}
                        className="bg-[var(--color-bg-secondary)] p-4 rounded-lg"
                      >
                        <h4 className="font-medium text-sm text-[var(--color-text-primary)] mb-2">
                          {metric}
                        </h4>
                        <div className="text-2xl font-bold text-[var(--color-text-primary)] mb-1">
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
                      console.log("Share by Email clicked");
                    }}
                    className="flex items-center gap-2"
                  >
                    <Mail className="w-4 h-4" />
                    Share by Email
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      console.log("Share on Slack clicked");
                    }}
                    className="flex items-center gap-2"
                  >
                    <MessageSquare className="w-4 h-4" />
                    Share on Slack
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

const ChannelNode = ({ data }: { data: any }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const color = data.color || getRandomColor();

  return (
    <>
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
      <div
        className={`px-6 py-4 rounded-lg shadow-lg border-2 min-w-[140px] text-center cursor-pointer transition-colors text-white relative ${color.bg} ${color.border} ${color.hover}`}
        style={{ minWidth: "140px", minHeight: "82px" }}
      >
        <div className="font-semibold text-sm">{data.label}</div>
        <div className="text-xs my-1 mb-5 pb-2 opacity-90">Channel</div>

        {/* Action Buttons */}
        <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1 my-2">
          <Dialog open={modalOpen} onOpenChange={setModalOpen}>
            <DialogTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
                title="View Channel"
              >
                <Eye className="w-3 h-3 text-white" />
              </button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle className="capitalize">
                  {data.label} Channel
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <p className="text-[var(--color-text-secondary)]">
                  Channel performance and configuration details for {data.label}
                  .
                </p>

                <div className="flex justify-end mt-6 gap-3">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="flex items-center gap-2"
                      >
                        <Share2 className="w-4 h-4" />
                        Share
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="flex items-center gap-2">
                        <Mail className="w-4 h-4" />
                        Share by Email
                      </DropdownMenuItem>
                      <DropdownMenuItem className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4" />
                        Share on Slack
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Expansion Indicator - only show if channel has tactics */}
        {Object.keys(
          snapshotData[data.stepId]?.channels[data.channelKey]?.tactics || {},
        ).length > 0 && (
          <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-1/2">
            <div className="w-6 h-6 bg-white border-2 border-[var(--color-border-default)] rounded-full flex items-center justify-center shadow-sm">
              {data.isSelected ? (
                <span className="text-xs font-bold text-[var(--color-text-tertiary)]">
                  -
                </span>
              ) : (
                <span className="text-xs font-bold text-[var(--color-text-tertiary)]">
                  +
                </span>
              )}
            </div>
          </div>
        )}
      </div>
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
    </>
  );
};

const TacticNode = ({ data }: { data: any }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const color = data.color || getRandomColor();

  return (
    <>
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
      <div
        className={`px-4 py-3 rounded-lg shadow-md border-2 min-w-[120px] text-center cursor-pointer transition-colors text-white relative ${color.bg} ${color.border} ${color.hover}`}
        style={{ minWidth: "120px", minHeight: "72px" }}
      >
        <div className="font-medium text-sm">{data.label}</div>
        <div className="text-xs my-1 mb-5 opacity-90">Tactic</div>

        {/* Action Buttons */}
        <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 flex gap-1">
          <Dialog open={modalOpen} onOpenChange={setModalOpen}>
            <DialogTrigger asChild>
              <button
                className="w-5 h-5 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition-colors"
                title="View Tactic"
              >
                <Eye className="w-3 h-3 text-white" />
              </button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle className="capitalize">
                  {data.label} Tactic
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <p className="text-[var(--color-text-secondary)]">
                  Tactic performance details and configuration for {data.label}.
                </p>

                <div className="flex justify-end mt-6 gap-3">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="flex items-center gap-2"
                      >
                        <Share2 className="w-4 h-4" />
                        Share
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="flex items-center gap-2">
                        <Mail className="w-4 h-4" />
                        Share by Email
                      </DropdownMenuItem>
                      <DropdownMenuItem className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4" />
                        Share on Slack
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </>
  );
};

const nodeTypes: NodeTypes = {
  objective: ObjectiveNode,
  channel: ChannelNode,
  tactic: TacticNode,
};

// Generate interactive nodes and edges with expansion logic
const generateInteractiveNodes = (
  selectedObjective: string | null,
  selectedChannel: string | null,
) => {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Match original positioning constants
  const objectiveKeys = Object.keys(snapshotData);
  const objectiveSpacing = 236;
  const startX = 20; // Start with 20px padding from left edge
  const startY = 24; // Start with 24px padding from top edge

  objectiveKeys.forEach((key, index) => {
    const objective = snapshotData[key as keyof typeof snapshotData];
    const objectiveId = `objective-${key}`;
    const isSelected = selectedObjective === key;

    // Create objective node (matches original positioning)
    nodes.push({
      id: objectiveId,
      type: "objective",
      position: { x: startX + index * objectiveSpacing, y: startY },
      data: {
        step_name: objective.step_name,
        objective: objective.objective,
        effectivenessKPI: objective.effectivenessKPI,
        efficiencyKPI: objective.efficiencyKPI,
        supportingMetrics: objective.supportingMetrics,
        color: getRandomColor(),
        stepId: key,
        isSelected,
      },
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
        const channelDisplayName =
          channelKey.charAt(0).toUpperCase() + channelKey.slice(1);

        // Create channel node
        nodes.push({
          id: channelId,
          type: "channel",
          position: {
            x: baseChannelX + channelStartX + channelIndex * channelSpacing,
            y: 308, // Match original channel Y position
          },
          data: {
            label: channelDisplayName,
            channelKey: channelKey,
            stepId: key,
            isSelected: channelIsSelected,
            color: getRandomColor(),
          },
        });

        // Create edge from objective to channel
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
          const channel = objective.channels[channelKey];
          const tacticKeys = Object.keys(channel.tactics || {});
          const tacticSpacing = 140;
          const tacticStartX = (-(tacticKeys.length - 1) * tacticSpacing) / 2;

          tacticKeys.forEach((tacticKey, tacticIndex) => {
            const tacticId = `tactic-${key}-${channelKey}-${tacticKey}`;
            const tacticDisplayName = tacticKey
              .replace(/_/g, " ")
              .toUpperCase();

            // Create tactic node
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
                y: 486, // Match original tactic Y position
              },
              data: {
                label: tacticDisplayName,
                color: getRandomColor(),
              },
            });

            // Create edge from channel to tactic
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

// Interactive React Flow Component
const InteractiveReactFlowComponent = () => {
  const [selectedObjective, setSelectedObjective] = useState<string | null>(
    null,
  );
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);

  const { nodes, edges } = generateInteractiveNodes(
    selectedObjective,
    selectedChannel,
  );

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
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

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={onNodeClick}
      minZoom={0.5}
      maxZoom={2}
      defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={true}
      zoomOnDoubleClick={false}
      panOnDrag={true}
      proOptions={{ hideAttribution: true }}
      className="react-flow-subflows-example"
    >
      <Background color="#f1f5f9" />
      <Controls />
    </ReactFlow>
  );
};

// Main Component
const ChannelControlsSnapshot = () => {
  return (
    <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-dashboard-gray-900 mb-2">
          Marketing Strategies Snapshot
        </h3>
        <p className="text-sm text-dashboard-gray-600">
          Frozen view of the marketing strategies at the time this report was
          generated.
        </p>
      </div>

      <div className="h-96 w-full relative flex flex-col flex-grow">
        <ReactFlowProvider>
          <InteractiveReactFlowComponent />
        </ReactFlowProvider>
      </div>
    </div>
  );
};

export default ChannelControlsSnapshot;
