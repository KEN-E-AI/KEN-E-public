/**
 * Standard layout constants for knowledge graph visualizations
 * These values ensure consistency across all knowledge graph pages
 */

export const DIAGRAM_LAYOUT = {
  // Node dimensions
  NODE_CIRCLE_SIZE: 72, // Circle badge size (px)
  NODE_ICON_SIZE: 48, // Icon size within circle (px)
  NODE_TEXT_WIDTH: 200, // Fixed width for text (px)

  // Spacing
  VERTICAL_SPACING: 224, // Y offset from parent to children (px)
  HORIZONTAL_GAP: 15, // Minimum gap between nodes (px)
  // NODE_TOTAL_WIDTH calculation:
  // Visual node width = NODE_TEXT_WIDTH - overlap + NODE_CIRCLE_SIZE
  //                   = 200 - 12 + 72 = 260px
  // Add HORIZONTAL_GAP for minimum spacing between nodes
  // Total = 260 + 15 = 275px
  NODE_TOTAL_WIDTH: 275, // Total node width including gap (px)

  // Initial positioning
  PARENT_NODE_X: 300, // Parent node X position (px)
  PARENT_NODE_Y: 50, // Parent node Y position (px)

  // Canvas viewport
  DEFAULT_VIEWPORT: {
    x: 250,
    y: 50,
    zoom: 1,
  },
} as const;

export const SCROLL_AMOUNT = 300; // Pixels to scroll on chevron click

export const CARD_HEIGHTS = {
  FULL: "h-[600px]",
  CONTENT: "h-[520px]",
} as const;
