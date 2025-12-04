/**
 * Layout calculation utilities for knowledge graph visualizations
 * Pure functions for calculating node positions in React Flow diagrams
 */

import { DIAGRAM_LAYOUT } from "../constants/layout";

/**
 * Calculate horizontal starting position for centered child nodes
 * @param nodeCount Number of child nodes to position
 * @returns X coordinate for first node
 */
export function calculateCenteredStartX(nodeCount: number): number {
  const totalWidth =
    nodeCount * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH - DIAGRAM_LAYOUT.HORIZONTAL_GAP;
  return DIAGRAM_LAYOUT.PARENT_NODE_X - totalWidth / 2;
}

/**
 * Calculate X position for a specific child node in centered layout
 * @param index Zero-based index of the node
 * @param nodeCount Total number of nodes
 * @returns X coordinate for the node
 */
export function calculateChildNodeX(index: number, nodeCount: number): number {
  const startX = calculateCenteredStartX(nodeCount);
  return startX + index * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
}

/**
 * Calculate Y position for child nodes
 * @returns Y coordinate for child nodes
 */
export function calculateChildNodeY(): number {
  return DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING;
}
