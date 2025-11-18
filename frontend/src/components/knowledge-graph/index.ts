/**
 * Knowledge Graph Component Library
 * Reusable components for consistent UX across knowledge graph pages
 */

// Core components
export { KnowledgeGraphCard } from "./core/KnowledgeGraphCard";
export { ModeSelector } from "./core/ModeSelector";
export { HorizontalScrollList } from "./core/HorizontalScrollList";
export { EmptyState } from "./core/EmptyState";
export { BorderedSection } from "./core/BorderedSection";
export { SectionHeader } from "./core/SectionHeader";

// Item cards
export { HorizontalScrollItem } from "./item-card/HorizontalScrollItem";
export { ScrollChevronButton } from "./item-card/ScrollChevronButton";

// Visualization components
export { GraphVisualization } from "./visualization/GraphVisualization";
export { GraphVisualizationCard } from "./visualization/GraphVisualizationCard";

// Side sheet components
export { KnowledgeGraphSideSheet } from "./side-sheet/KnowledgeGraphSideSheet";
export { SideSheetNestedList } from "./side-sheet/SideSheetNestedList";

// Hooks
export { useScrollPosition } from "./hooks/useScrollPosition";
export { useUnsavedChanges } from "./hooks/useUnsavedChanges";

// Constants
export {
  DIAGRAM_LAYOUT,
  SCROLL_AMOUNT,
  CARD_HEIGHTS,
} from "./constants/layout";
export {
  DEFAULT_REACT_FLOW_CONFIG,
  DEFAULT_EDGE_STYLE,
} from "./constants/reactFlowConfig";

// Types
export type {
  KnowledgeGraphItem,
  ModeConfig,
  ScrollableItemProps,
  HorizontalScrollItemVisualProps,
  KnowledgeGraphCardProps,
  GraphVisualizationProps,
  NestedListItem,
  SideSheetNestedListProps,
  EmptyStateProps,
} from "./types";
