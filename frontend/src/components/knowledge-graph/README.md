# Knowledge Graph Component Library

Reusable components for building consistent knowledge graph visualizations across the application.

## Overview

This library provides a set of composable components that handle common patterns in knowledge graph pages:

- Horizontal scrollable lists with chevron navigation
- React Flow visualizations with consistent styling
- Side sheets for viewing/editing items
- Mode selectors for switching between views

## Components

### Core Components

#### `KnowledgeGraphCard`

Card wrapper with consistent header, icon, tooltip, and actions.

```tsx
<KnowledgeGraphCard
  title="Product Categories"
  icon={Blocks}
  tooltip="Create product categories to organize your products"
  actions={<Button>Add</Button>}
>
  {/* Content */}
</KnowledgeGraphCard>
```

#### `ModeSelector`

Segmented control for switching between modes.

```tsx
<ModeSelector
  modes={[
    { value: "strengths", label: "Strengths" },
    { value: "weaknesses", label: "Weaknesses" },
  ]}
  value={currentMode}
  onChange={setMode}
/>
```

#### `HorizontalScrollList`

Scrollable list with automatic chevron buttons.

```tsx
<HorizontalScrollList
  items={categories}
  selectedId={selectedId}
  onItemClick={handleClick}
  renderItem={(item, isSelected) => (
    <HorizontalScrollItem
      label={item.display_name}
      icon={Blocks}
      bgColor="bg-brand-light-blue bg-opacity-30"
      iconBgColor="bg-brand-light-blue"
      isSelected={isSelected}
      onClick={() => {}}
    />
  )}
/>
```

#### `EmptyState`

Consistent empty state messaging.

```tsx
<EmptyState message="Select a category to view details" height="h-[600px]" />
```

### Visualization Components

#### `GraphVisualization`

React Flow wrapper with standard configuration.

```tsx
<GraphVisualization
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  onNodeClick={handleNodeClick}
/>
```

#### `GraphVisualizationCard`

Combined card + React Flow component.

```tsx
<GraphVisualizationCard
  title="Products and Services"
  icon={Package}
  tooltip="Your flagship products"
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  onNodeClick={handleNodeClick}
  showEmpty={!selectedId}
  emptyMessage="Select a category to view products"
/>
```

### Side Sheet Components

#### `KnowledgeGraphSideSheet`

Side sheet with edit/view modes and action buttons.

```tsx
<KnowledgeGraphSideSheet
  open={isOpen}
  onOpenChange={setIsOpen}
  title="Product Category"
  icon={Blocks}
  isEditing={isEditing}
  onEdit={() => setIsEditing(true)}
  onSave={handleSave}
  onCancel={handleCancel}
  onDelete={handleDelete}
  hasEditAccess={hasEditAccess}
>
  {/* Form fields or view content */}
</KnowledgeGraphSideSheet>
```

#### `SideSheetNestedList`

List of nested items (Value Propositions, Tactics, etc.) within side sheets.

```tsx
<SideSheetNestedList
  title="Value Propositions"
  tooltip="Reasons customers choose your products"
  items={valuePropositions}
  onAdd={() => setIsCreateModalOpen(true)}
  onEdit={handleEdit}
  onDelete={handleDelete}
  hasEditAccess={hasEditAccess}
  isEditingParent={isEditing}
/>
```

### Item Card Components

#### `HorizontalScrollItem`

Visual representation of items in horizontal scroll lists.

```tsx
<HorizontalScrollItem
  label="Software Products"
  sublabel="Product Category"
  icon={Blocks}
  bgColor="bg-brand-light-blue bg-opacity-30"
  iconBgColor="bg-brand-light-blue"
  isSelected={isSelected}
  onClick={handleClick}
/>
```

## Hooks

### `useScrollPosition`

Manages horizontal scroll state and chevron visibility.

```tsx
const scrollRef = useRef<HTMLDivElement>(null);
const { canScrollLeft, canScrollRight, scrollLeft, scrollRight } =
  useScrollPosition(scrollRef, [items]);
```

### `useUnsavedChanges`

Detects unsaved changes in forms.

```tsx
const hasChanges = useUnsavedChanges(originalData, formData, isEditing);
```

## Constants

### Layout Constants

```tsx
import { DIAGRAM_LAYOUT, CARD_HEIGHTS } from "@/components/knowledge-graph";

// Use in React Flow positioning
const x = DIAGRAM_LAYOUT.PARENT_NODE_X;
const y = DIAGRAM_LAYOUT.PARENT_NODE_Y;

// Use for card heights
<Card className={CARD_HEIGHTS.FULL} />;
```

### React Flow Configuration

```tsx
import {
  DEFAULT_REACT_FLOW_CONFIG,
  DEFAULT_EDGE_STYLE,
} from "@/components/knowledge-graph";

// Applied automatically by GraphVisualization
```

## Examples

See the following pages for implementation examples:

- `/knowledge/products` - Basic 2-level hierarchy without mode selector
- `/knowledge/account` - 2-level hierarchy with mode selector
- `/knowledge/competitors` - Complex 3-level hierarchy with mode selector

## Design Principles

1. **Composability**: Components can be mixed and matched
2. **Consistency**: All pages share the same visual patterns
3. **Flexibility**: Generic types allow any data structure
4. **Type Safety**: Full TypeScript support
5. **Accessibility**: Proper ARIA labels and keyboard navigation

## Migration Guide

When refactoring existing pages:

1. Replace custom cards with `KnowledgeGraphCard`
2. Replace scroll logic with `HorizontalScrollList` and `useScrollPosition`
3. Replace React Flow boilerplate with `GraphVisualizationCard`
4. Replace side sheets with `KnowledgeGraphSideSheet`
5. Use `SideSheetNestedList` for nested data

This typically reduces page code by 50-70% while improving consistency.
