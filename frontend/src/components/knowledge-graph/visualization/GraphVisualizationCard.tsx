import { KnowledgeGraphCard } from "../core/KnowledgeGraphCard";
import { GraphVisualization } from "./GraphVisualization";
import { EmptyState } from "../core/EmptyState";
import { CARD_HEIGHTS } from "../constants/layout";
import type { Node, Edge } from "reactflow";
import type React from "react";

interface GraphVisualizationCardProps {
  title: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  tooltip?: string;
  nodes: Node[];
  edges: Edge[];
  nodeTypes: Record<string, React.ComponentType<any>>;
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
  onNodeDoubleClick?: (event: React.MouseEvent, node: Node) => void;
  isLoading?: boolean;
  emptyMessage?: string;
  showEmpty?: boolean;
}

/**
 * Combined Card + React Flow component
 * Wraps GraphVisualization in a KnowledgeGraphCard with consistent styling
 */
export function GraphVisualizationCard({
  title,
  icon,
  tooltip,
  nodes,
  edges,
  nodeTypes,
  onNodeClick,
  onNodeDoubleClick,
  isLoading = false,
  emptyMessage = "Select an item to view details.",
  showEmpty = false,
}: GraphVisualizationCardProps) {
  if (showEmpty) {
    return <EmptyState message={emptyMessage} height={CARD_HEIGHTS.FULL} />;
  }

  return (
    <KnowledgeGraphCard
      title={title}
      icon={icon}
      tooltip={tooltip}
      height={CARD_HEIGHTS.FULL}
    >
      <div className={CARD_HEIGHTS.CONTENT}>
        <GraphVisualization
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={onNodeDoubleClick}
          isLoading={isLoading}
          height="h-full"
        />
      </div>
    </KnowledgeGraphCard>
  );
}
