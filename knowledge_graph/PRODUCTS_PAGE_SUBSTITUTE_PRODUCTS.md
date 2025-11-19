# Products Page - Substitute Products Integration

**Date**: 2025-11-19
**Status**: Phase 1 Complete, Phase 2 Pending
**Branch**: `feature/competitive-knowledge-base`
**Related**: `SUBSTITUTE_PRODUCTS_IMPLEMENTATION_PLAN.md`

---

## Overview

This document tracks the implementation of **bidirectional substitute product visualization** - showing SubstituteProducts on the Products page (reverse of showing Products on Competitors page).

### Goal
When a user selects a Product on `/knowledge/products`, show linked SubstituteProducts in a third row of the React Flow diagram, with ability to view, navigate to edit, and unlink.

---

## Design Requirements

### 1. React Flow Visualization
- **3-Row Layout**: ProductCategory → Product → SubstituteProducts
- **Styling**: Use same yellow color and Package icon from Competitors page
- **Edge Direction**: Product → SubstituteProduct (matches MAY_BE_SUBSTITUTED_FOR)
- **"+" Button**: On Product node to link additional substitute products

### 2. Side Sheet for SubstituteProduct
- **Read-only view** of SubstituteProduct details
- **Edit button** → navigates to `/knowledge/competitors` with auto-selection
- **Unlink button** → removes MAY_BE_SUBSTITUTED_FOR relationship
- **Button label**: "Unlink" (not "Delete")

### 3. ValuePropositions Handling
- **Stay in Product side sheet** (don't move to React Flow)
- SubstituteProducts are third-level visualization (separate concern)

---

## Phase 1: Backend + Service Layer ✅ (Commit: c5b2a65)

### Backend Changes

**File**: `api/src/kene_api/routers/knowledge_graph/competitive.py`

**Added `product_node_id` filter** to `list_substitute_products` endpoint:
```python
async def list_substitute_products(
    account_id: str,
    competitor_node_id: str | None = Query(None, ...),
    product_node_id: str | None = Query(None, ...),  # NEW
    ...
)
```

**Validation**: Cannot filter by both `competitor_node_id` and `product_node_id`

**Query Logic**:
```python
if product_node_id:
    # Reverse MAY_BE_SUBSTITUTED_FOR query
    query = """
    MATCH (p:Product {node_id: $product_node_id})-[:BELONGS_TO]->(acc:Account)
    MATCH (p)-[:MAY_BE_SUBSTITUTED_FOR]->(sub:SubstituteProduct)-[:BELONGS_TO]->(acc)
    MATCH (comp:Competitor)-[:OFFERS_PRODUCT]->(sub)
    RETURN sub as node, comp.node_id as parent_node_id
    ORDER BY sub.product_name
    """
```

### Frontend Service Layer

**File**: `frontend/src/services/substituteProductService.ts`

```typescript
async list(
  accountId: AccountId,
  competitorId?: string,
  productNodeId?: string,  // NEW
  skip = 0,
  limit = 1000,
)
```

**File**: `frontend/src/queries/competitors.ts`

```typescript
export function useSubstituteProducts(
  accountId: string | null,
  competitorId: string | null,
  productNodeId?: string | null,  // NEW
  skip = 0,
  limit = 1000,
)
```

**Updated**: CompetitorsManagement to pass `null` for new parameter

### Frontend UI Preparation

**File**: `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Added**:
- Imports: `useSubstituteProducts`, `useLinkProductToSubstitute`, `useUnlinkProductFromSubstitute`, `SubstituteProduct` type, `SubstituteProductNode` component
- Data loading: `substituteProducts` query filtered by `selectedProductId`
- State: `selectedSubstituteProduct`, `selectedSubstituteProductId`
- Mutations: `linkProductMutation`, `unlinkProductMutation`
- Node types: Added `substituteProductNode: SubstituteProductNode`

---

## Phase 2: UI Integration (PENDING)

### Implementation Steps

#### Step 1: Update `generateNodes()` Function

**Current State** (lines ~467-530):
- Row 1: ProductCategory (parent node)
- Row 2: Products (children)

**Required Changes**:
Add third row for SubstituteProducts when a Product is selected:

```typescript
// After Product nodes are generated (around line 527):
if (selectedProductId && substituteProducts.length > 0) {
  const substituteWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
  const substituteTotalWidth = substituteProducts.length * substituteWidth - gap;
  const substituteStartX = DIAGRAM_LAYOUT.PARENT_NODE_X - substituteTotalWidth / 2;
  const substituteY = DIAGRAM_LAYOUT.PARENT_NODE_Y + (DIAGRAM_LAYOUT.VERTICAL_SPACING * 2);

  substituteProducts.forEach((sub, index) => {
    nodes.push({
      id: sub.node_id,
      type: "substituteProductNode",
      position: {
        x: substituteStartX + index * substituteWidth,
        y: substituteY,
      },
      data: {
        label: sub.product_name,
        showHandle: false,
        isSelected: selectedSubstituteProductId === sub.node_id,
        onAddProduct: () => {}, // No add functionality from Products page
      },
    });
  });
}
```

**Also update Product node** to add "+" button:
```typescript
// In Product node data (around line 508):
data: {
  label: product.product_name,
  showHandle: selectedProductId === product.node_id, // Show "+" on selected product
  isSelected: selectedProductId === product.node_id,
  onAddSubstitute: () => handleOpenLinkSubstituteDialog(), // NEW
},
```

---

#### Step 2: Update `generateEdges()` Function

**Current State** (lines ~533-559):
- Category → Product edges

**Required Changes**:
Add Product → SubstituteProduct edges:

```typescript
// After Category → Product edges (around line 556):
if (selectedProductId && selectedProduct) {
  substituteProducts.forEach((sub) => {
    edges.push({
      id: `${selectedProductId}-${sub.node_id}`,
      source: selectedProductId,
      target: sub.node_id,
      type: "smoothstep",
      style: DEFAULT_EDGE_STYLE,
      sourceHandle: "bottom",
      targetHandle: "top",
    });
  });
}
```

---

#### Step 3: Update `handleNodeClick()` Function

**Location**: Around line 480

**Add case for SubstituteProduct nodes**:
```typescript
// After existing product node case:
if (node.type === "substituteProductNode") {
  const sub = substituteProducts.find((s) => s.node_id === node.id);
  if (sub) {
    setSelectedSubstituteProduct(sub);
    setSelectedSubstituteProductId(sub.node_id);
    setContextMenuType("substitute"); // NEW context type
    setIsContextMenuOpen(true);
  }
  return;
}
```

---

#### Step 4: Update Context Menu Type

**Location**: Around line 136

**Change**:
```typescript
const [contextMenuType, setContextMenuType] = useState<
  "category" | "product" | "substitute" | null  // Add "substitute"
>(null);
```

---

#### Step 5: Add Navigation Handler

**Location**: After other handlers (around line 450)

```typescript
// Handle navigating to Competitors page to edit a substitute product
const handleNavigateToSubstituteEdit = () => {
  if (!selectedSubstituteProduct) return;
  // Navigate to Competitors page with selected substitute product and auto-edit mode
  navigate("/knowledge/competitors", {
    state: {
      selectedSubstituteProductId: selectedSubstituteProduct.node_id,
      competitorNodeId: selectedSubstituteProduct.competitor_node_id,
      autoEdit: true,
    },
  });
};

// Handle unlinking substitute product from product
const handleUnlinkSubstituteProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedProduct || !selectedSubstituteProduct) return;

  try {
    startOperation("Unlinking substitute product...");

    await unlinkProductMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      substituteProductId: selectedSubstituteProduct.node_id,
      productNodeId: selectedProduct.node_id,
    });

    toast({
      title: "Success",
      description: "Substitute product unlinked successfully",
    });

    setIsContextMenuOpen(false);
    setSelectedSubstituteProduct(null);
    setSelectedSubstituteProductId(null);
  } catch (error) {
    console.error("Failed to unlink substitute product:", error);
    toast({
      title: "Error",
      description: "Failed to unlink substitute product",
      variant: "destructive",
    });
  } finally {
    endOperation();
  }
};
```

---

#### Step 6: Update Side Sheet Props

**Location**: Find the main `KnowledgeGraphSideSheet` component (around line 1330)

**Add conditional logic for substitute products**:

```typescript
// In title prop (around line 1350):
title={
  contextMenuType === "category"
    ? "Product Category"
    : contextMenuType === "product"
      ? selectedProduct?.product_name || "Product"
      : contextMenuType === "substitute"
        ? selectedSubstituteProduct?.product_name || "Substitute Product"
        : ""
}

// In icon prop (around line 1360):
icon={
  contextMenuType === "category"
    ? Blocks
    : contextMenuType === "product"
      ? Package
      : contextMenuType === "substitute"
        ? Package  // Same icon as Product
        : Package
}

// In onEdit prop (around line 1375):
onEdit={
  contextMenuType === "substitute"
    ? handleNavigateToSubstituteEdit
    : () => setIsEditing(true)
}

// In onDelete prop (around line 1380):
onDelete={
  contextMenuType === "substitute"
    ? handleUnlinkSubstituteProduct
    : () => {
        setIsContextMenuOpen(false);
        if (contextMenuType === "category") {
          setIsDeleteDialogOpen(true);
        } else if (contextMenuType === "product") {
          setIsDeleteProductDialogOpen(true);
        }
      }
}

// In deleteButtonLabel prop (NEW):
deleteButtonLabel={
  contextMenuType === "substitute"
    ? "Unlink"
    : undefined
}
```

---

#### Step 7: Add SubstituteProduct Content in Side Sheet

**Location**: In the side sheet children section (around line 1470)

**Add after existing content**:

```typescript
{/* Add after the product view section */}
) : contextMenuType === "substitute" ? (
  // SubstituteProduct view (read-only with navigation to edit)
  <div className="space-y-4">
    <div>
      <Label>Product Name</Label>
      <p className="text-sm text-muted-foreground mt-1">
        {selectedSubstituteProduct?.product_name}
      </p>
    </div>
    <div>
      <Label>Description</Label>
      <p className="text-sm text-muted-foreground mt-1">
        {selectedSubstituteProduct?.description}
      </p>
    </div>
    {selectedSubstituteProduct?.product_detail_page && (
      <div>
        <Label>Product Page</Label>
        <a
          href={selectedSubstituteProduct.product_detail_page}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:underline mt-1 block"
        >
          {selectedSubstituteProduct.product_detail_page}
        </a>
      </div>
    )}
    <div className="rounded-md bg-muted p-3 mt-4">
      <p className="text-xs text-muted-foreground">
        This competitor offering may substitute your product. Click "Unlink"
        to remove this relationship. Click "Edit" to manage details on the
        Competitors page.
      </p>
    </div>
  </div>
) : (
  // Existing category view...
```

---

#### Step 8: Update useMemo Dependencies

**Location**: Around line 940

**Find**:
```typescript
const nodes = useMemo(
  () => generateNodes(),
  [selectedCategory, products, selectedProductId],
);

const edges = useMemo(
  () => generateEdges(),
  [selectedCategory, selectedCategoryId, products, selectedProductId],
);
```

**Update to include substitute products**:
```typescript
const nodes = useMemo(
  () => generateNodes(),
  [selectedCategory, products, selectedProductId, substituteProducts, selectedSubstituteProductId],
);

const edges = useMemo(
  () => generateEdges(),
  [selectedCategory, selectedCategoryId, products, selectedProductId, substituteProducts],
);
```

---

## Implementation Checklist

### Phase 1: Backend + Service Layer ✅
- [x] Add `product_node_id` filter to backend endpoint
- [x] Add validation for dual filtering
- [x] Implement reverse relationship query
- [x] Update `substituteProductService.list()` method
- [x] Update `useSubstituteProducts` hook
- [x] Update CompetitorsManagement hook call
- [x] Add imports to ProductCategoriesManagement
- [x] Add substitute products data loading
- [x] Add state for selected substitute product
- [x] Add link/unlink mutations
- [x] Update node types

### Phase 2: UI Integration (PENDING)
- [ ] Update `generateNodes()` for 3-row layout
- [ ] Add "+" button to Product node when selected
- [ ] Update `generateEdges()` for Product → SubstituteProduct
- [ ] Update `contextMenuType` type definition
- [ ] Add `handleNodeClick()` case for SubstituteProducts
- [ ] Add `handleNavigateToSubstituteEdit()` handler
- [ ] Add `handleUnlinkSubstituteProduct()` handler
- [ ] Update side sheet title for SubstituteProducts
- [ ] Update side sheet icon for SubstituteProducts
- [ ] Update side sheet onEdit for SubstituteProducts
- [ ] Update side sheet onDelete for SubstituteProducts
- [ ] Add SubstituteProduct content section
- [ ] Update useMemo dependencies
- [ ] Run typecheck and format
- [ ] Test complete workflow

---

## Related Commits

### Substitute Products Feature (All Commits)
1. `f922b4a` - Backend + frontend services (phases 1-3)
2. `72d0bc3` - UI integration for Competitors page (phase 4)
3. `a8fa78d` - Fix execute_write_query for link/unlink
4. `e3c42fa` - Fix edge direction
5. `58e9cf8` - Add Product edit navigation
6. `21900a5` - Add deleteButtonLabel prop
7. `e95cca7` - Fix side sheet rendering
8. `a5b6a2d` - Remove duplicate side sheet
9. `13f9012` - Auto-open product for editing
10. `d8a5724` - Pass category_node_id in navigation
11. `c5b2a65` - **Products page phase 1** (THIS SESSION)

---

## Key Design Patterns

### 1. Bidirectional Relationships
```
Competitors Page: SubstituteProduct → Products (shows what your products are threatened by)
Products Page: Product → SubstituteProducts (shows what threatens this product)
```

### 2. Cross-Page Navigation
```
Products → Competitors: Edit SubstituteProduct
Competitors → Products: Edit Product
```

Both directions use navigation state with auto-selection and auto-edit mode.

### 3. Single Source of Truth
- **Products** are edited on `/knowledge/products`
- **SubstituteProducts** are edited on `/knowledge/competitors`
- Relationship management (link/unlink) available on both pages

---

## File Locations

### Backend
- Endpoint: `api/src/kene_api/routers/knowledge_graph/competitive.py:661-750`
- Service: Uses `neo4j.execute_query()` directly (no service method added)

### Frontend Services
- Service: `frontend/src/services/substituteProductService.ts:40-56`
- Hook: `frontend/src/queries/competitors.ts:389-408`

### Frontend Components
- Products Page: `frontend/src/components/products/ProductCategoriesManagement.tsx`
  - Imports: Lines 31-38
  - Data Loading: Lines 190-203
  - State: Lines 199-203
  - Mutations: Lines 210-211
  - Node Types: Line 463
  - **PENDING**: generateNodes(), generateEdges(), handleNodeClick(), side sheet

- Competitors Page: `frontend/src/components/competitors/CompetitorsManagement.tsx`
  - Updated hook call: Line 241 (added `null` parameter)

---

## Testing Checklist (Phase 2)

### Backend Tests
- [ ] `GET /substitute-products?product_node_id=xyz` returns correct substitutes
- [ ] Cannot filter by both `competitor_node_id` and `product_node_id` (400 error)
- [ ] Includes `competitor_node_id` in response for each substitute

### Frontend Tests - Products Page
- [ ] Select a Product → SubstituteProduct nodes appear in third row
- [ ] SubstituteProducts use yellow color and Package icon
- [ ] Edges connect Product → SubstituteProduct
- [ ] Click SubstituteProduct node → side sheet opens
- [ ] Side sheet shows SubstituteProduct details (read-only)
- [ ] Side sheet has "Edit" and "Unlink" buttons
- [ ] Click "Edit" → navigates to Competitors page
- [ ] Click "Unlink" → removes relationship, node disappears
- [ ] Product node shows "+" button when selected
- [ ] ValuePropositions still work in Product side sheet

### Frontend Tests - Cross-Page Navigation
- [ ] Products → Competitors: Edit button works
- [ ] Competitors → Products: Edit button works (already tested)
- [ ] Navigation state is cleared after processing
- [ ] Refreshing page doesn't re-trigger navigation

---

## Known Issues & Considerations

### Issue 1: Product Node Needs "+" Button Visibility Logic
The ProductNode component may need to accept a `showHandle` prop similar to SubstituteProductNode. Check `ProductFlowNodes.tsx` to see if this exists.

### Issue 2: Third Row Layout
Adding a third row may require adjusting `DIAGRAM_LAYOUT.VERTICAL_SPACING` or the diagram height to ensure all nodes are visible.

### Issue 3: Auto-Navigation to Competitors Page
Similar to the Product edit navigation, we need to implement auto-selection on the Competitors page when navigating from Products. This requires:
- useEffect in CompetitorsManagement to handle navigation state
- Select the correct competitor
- Select the correct substitute product
- Open side sheet in edit mode

---

## Next Session Preparation

### Before Starting Phase 2:
1. Review this document thoroughly
2. Have ProductCategoriesManagement.tsx open
3. Reference CompetitorsManagement.tsx for similar patterns
4. Test incrementally - don't implement everything at once

### Recommended Order:
1. Steps 1-2: Generate nodes and edges (get visualization working)
2. Step 3-4: Handle clicks and context type
3. Steps 5-7: Add handlers and side sheet content
4. Step 8: Update dependencies
5. Test and fix issues

### Similar Code References:
- CompetitorsManagement substitute-products mode: Lines 712-748 (generateNodes)
- CompetitorsManagement substitute-products mode: Lines 788-800 (generateEdges)
- CompetitorsManagement Product side sheet: Lines 3014-3050 (content)
- CompetitorsManagement navigation: Lines 999-1011 (handleNavigateToProductEdit)

---

## Session Summary

**Time**: ~1 hour
**Files Modified**: 5 files
**Lines Changed**: +94, -17
**Tests**: Backend logic tested via TypeScript compilation
**Status**: Ready for Phase 2 UI integration

**Next Session**: Implement UI integration (Steps 1-8) to complete the feature.
