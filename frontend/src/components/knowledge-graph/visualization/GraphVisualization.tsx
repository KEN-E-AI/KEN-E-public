import { ReactFlow, Controls, Background } from "reactflow";
import { Loader2 } from "lucide-react";
import "reactflow/dist/style.css";
import { DEFAULT_REACT_FLOW_CONFIG } from "../constants/reactFlowConfig";
import { DIAGRAM_LAYOUT } from "../constants/layout";
import type { GraphVisualizationProps } from "../types";

/**
 * Reusable React Flow wrapper with standard configuration
 * Provides consistent behavior across all knowledge graph visualizations
 */
export function GraphVisualization({
  nodes,
  edges,
  nodeTypes,
  onNodeClick,
  onNodeDoubleClick,
  isLoading = false,
  height = "h-full",
}: GraphVisualizationProps) {
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center ${height}`}>
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className={height}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        defaultViewport={DIAGRAM_LAYOUT.DEFAULT_VIEWPORT}
        {...DEFAULT_REACT_FLOW_CONFIG}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
