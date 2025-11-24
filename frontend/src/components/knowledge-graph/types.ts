import type React from "react";
import type { Node, Edge } from "reactflow";

/**
 * Base interface for all knowledge graph items
 */
export interface KnowledgeGraphItem {
  node_id: string;
  display_name: string;
  description: string;
}

/**
 * Mode configuration for mode selector
 */
export interface ModeConfig<T extends string> {
  value: T;
  label: string;
}

/**
 * Props for scrollable list items
 */
export interface ScrollableItemProps<T extends KnowledgeGraphItem> {
  items: T[];
  selectedId: string | null;
  onItemClick: (item: T) => void;
  isLoading?: boolean;
  emptyMessage?: string;
  emptyMessageWithAction?: string;
  onAdd?: () => void;
  hasEditAccess?: boolean;
  renderItem: (item: T, isSelected: boolean) => React.ReactNode;
}

/**
 * Props for horizontal scroll item visual representation
 */
export interface HorizontalScrollItemVisualProps {
  label: string;
  sublabel?: string;
  icon: React.ComponentType<{
    className?: string;
    style?: React.CSSProperties;
  }>;
  bgColor: string;
  iconBgColor: string;
  isSelected: boolean;
  onClick: () => void;
}

/**
 * Props for knowledge graph card wrapper
 */
export interface KnowledgeGraphCardProps {
  title: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  tooltip?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  height?: string;
  className?: string;
}

/**
 * Props for graph visualization
 */
export interface GraphVisualizationProps {
  nodes: Node[];
  edges: Edge[];
  nodeTypes: Record<string, React.ComponentType<any>>;
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
  onNodeDoubleClick?: (event: React.MouseEvent, node: Node) => void;
  isLoading?: boolean;
  height?: string;
}

/**
 * Props for nested list items in side sheets
 */
export interface NestedListItem {
  node_id: string;
  display_name: string;
  description: string;
}

export interface SideSheetNestedListProps<T extends NestedListItem> {
  title: string;
  tooltip?: string;
  items: T[];
  isLoading?: boolean;
  onAdd?: () => void;
  onEdit?: (item: T) => void;
  onDelete?: (item: T) => void;
  hasEditAccess?: boolean;
  isEditingParent?: boolean;
}

/**
 * Empty state props
 */
export interface EmptyStateProps {
  message: string;
  height?: string;
}
