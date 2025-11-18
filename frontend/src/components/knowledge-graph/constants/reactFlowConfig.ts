import type { ProOptions } from "reactflow";

/**
 * Standard React Flow configuration
 * Applied consistently across all knowledge graph visualizations
 */

export const DEFAULT_REACT_FLOW_CONFIG = {
  minZoom: 0.5,
  maxZoom: 1.5,
  nodesDraggable: false,
  nodesConnectable: false,
  elementsSelectable: true,
  panOnScroll: true,
  zoomOnScroll: false,
  proOptions: { hideAttribution: true } as ProOptions,
} as const;

export const DEFAULT_EDGE_STYLE = {
  stroke: "#000",
  strokeWidth: 2,
} as const;
