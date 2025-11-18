# Substitute Products React Flow Implementation Plan

**Date**: 2025-11-18
**Goal**: Show Product nodes in React Flow when SubstituteProduct is selected, with side sheet to manage MAY_BE_SUBSTITUTED_FOR relationships

---

## Requirements Summary

Based on `/knowledge/products` page pattern and `competitor_requirements.md`:

1. **React Flow Diagram**: Show SubstituteProduct node → Product nodes (via MAY_BE_SUBSTITUTED_FOR relationship)
2. **Side Sheet for SubstituteProduct**: Include nested list of Value Propositions (like Products page)
3. **Side Sheet for Product Node**: Allow user to link/unlink Products to the selected SubstituteProduct
4. **No Product Creation**: Users cannot create new Products from competitors page, only link existing ones

---

## Data Model

### Relationships
```
SubstituteProduct ←[:OFFERS_PRODUCT]- Competitor
SubstituteProduct -[:HAS_VALUE_PROPOSITION]→ ValueProposition
Product -[:MAY_BE_SUBSTITUTED_FOR]→ SubstituteProduct
```

### Key Insight
- **ValuePropositions**: Shown in side sheet (nested list) - NOT in React Flow
- **Products**: Shown in React Flow diagram (nodes connected to SubstituteProduct)
- **Linking**: User selects from existing Products to create MAY_BE_SUBSTITUTED_FOR relationship

---

## Implementation Steps

### Phase 1: Backend API Updates

#### 1.1 Add `substitute_product_node_id` Filter to `list_products` Endpoint
**File**: `api/src/kene_api/routers/knowledge_graph/business.py:193-231`

**Changes:**
```python
@router.get("/{account_id}/products", response_model=ProductListResponse)
async def list_products(
    account_id: str,
    category_node_id: str | None = Query(None, description="Filter by category"),
    substitute_product_node_id: str | None = Query(
        None, description="Filter by substitute product (MAY_BE_SUBSTITUTED_FOR relationship)"
    ),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductListResponse:
    """List all products with optional pagination.

    Can filter by category_node_id OR substitute_product_node_id (not both).
    """
    # Validate: cannot filter by both
    if category_node_id and substitute_product_node_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot filter by both category_node_id and substitute_product_node_id"
        )
```

**Pattern**: Follow `list_opportunities` dual-filter pattern (business.py:677-782)

---

#### 1.2 Update `list_products_with_categories` Service Method
**File**: `api/src/kene_api/services/graph_sync_service.py:990-1074`

**Changes:**
- Add `substitute_product_node_id: str | None = None` parameter
- Add new query branch for substitute product filtering:

```python
async def list_products_with_categories(
    self,
    account_id: str,
    category_node_id: str | None = None,
    substitute_product_node_id: str | None = None,  # NEW
    skip: int = 0,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List products with category info OR filtered by substitute product."""

    if substitute_product_node_id:
        # NEW BRANCH: Query products that MAY_BE_SUBSTITUTED_FOR this substitute
        query = """
        MATCH (acc:Account {account_id: $account_id})
        MATCH (sub:SubstituteProduct {node_id: $substitute_product_node_id})
              <-[:MAY_BE_SUBSTITUTED_FOR]-(p:Product)-[:BELONGS_TO]->(acc)
        OPTIONAL MATCH (cat:ProductCategory)-[:INCLUDES_PRODUCT]->(p)
        RETURN p as node, acc.account_id as account_id, cat.node_id as category_node_id
        ORDER BY p.product_name
        """
        count_query = """
        MATCH (sub:SubstituteProduct {node_id: $substitute_product_node_id})
              <-[:MAY_BE_SUBSTITUTED_FOR]-(p:Product)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        RETURN count(p) as total
        """
        count_params = {
            "account_id": account_id,
            "substitute_product_node_id": substitute_product_node_id,
        }
    elif category_node_id:
        # EXISTING: Category filter
        # ... existing code ...
    else:
        # EXISTING: All products
        # ... existing code ...
```

**Notes:**
- Maintains N+1 prevention with OPTIONAL MATCH for category
- Follows same pattern as existing category filtering
- Returns same structure: `(products_list, total_count)`

---

### Phase 2: Backend Relationship Management API

#### 2.1 Create Endpoint to Link Product to SubstituteProduct
**File**: `api/src/kene_api/routers/knowledge_graph/competitive.py` (NEW FILE)

**Endpoint:**
```python
@router.post("/{account_id}/substitute-products/{substitute_id}/link-product")
async def link_product_to_substitute(
    account_id: str,
    substitute_id: str,
    product_node_id: str = Body(..., embed=True),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Create MAY_BE_SUBSTITUTED_FOR relationship between Product and SubstituteProduct.

    Cypher:
        MATCH (p:Product {node_id: $product_node_id})
        MATCH (s:SubstituteProduct {node_id: $substitute_id})
        MERGE (p)-[:MAY_BE_SUBSTITUTED_FOR]->(s)
        RETURN p, s
    """
```

**Alternative**: Use generic relationship endpoint if one exists

---

#### 2.2 Create Endpoint to Unlink Product from SubstituteProduct
**File**: `api/src/kene_api/routers/knowledge_graph/competitive.py`

**Endpoint:**
```python
@router.delete("/{account_id}/substitute-products/{substitute_id}/unlink-product/{product_node_id}")
async def unlink_product_from_substitute(
    account_id: str,
    substitute_id: str,
    product_node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Remove MAY_BE_SUBSTITUTED_FOR relationship.

    Cypher:
        MATCH (p:Product {node_id: $product_node_id})
              -[r:MAY_BE_SUBSTITUTED_FOR]->
              (s:SubstituteProduct {node_id: $substitute_id})
        DELETE r
        RETURN p, s
    """
```

---

### Phase 3: Frontend Service Layer Updates

#### 3.1 Update `productService.list()` Method
**File**: `frontend/src/services/productService.ts:39-50`

**Changes:**
```typescript
async list(
  accountId: AccountId,
  categoryNodeId?: string,
  substituteProductNodeId?: string,  // NEW
  skip = 0,
  limit = 1000,
): Promise<ProductListResponse> {
  const params: Record<string, any> = { skip, limit };
  if (categoryNodeId) params.category_node_id = categoryNodeId;
  if (substituteProductNodeId) params.substitute_product_node_id = substituteProductNodeId;  // NEW

  const response = await api.get(
    `/api/v1/knowledge-graph/${accountId}/products`,
    { params },
  );
  return response.data;
}
```

---

#### 3.2 Create Relationship Service Methods
**File**: `frontend/src/services/substituteProductService.ts` (update existing)

**Add methods:**
```typescript
async linkProduct(
  accountId: AccountId,
  substituteProductId: string,
  productNodeId: string,
): Promise<void> {
  await api.post(
    `/api/v1/knowledge-graph/${accountId}/substitute-products/${substituteProductId}/link-product`,
    { product_node_id: productNodeId }
  );
}

async unlinkProduct(
  accountId: AccountId,
  substituteProductId: string,
  productNodeId: string,
): Promise<void> {
  await api.delete(
    `/api/v1/knowledge-graph/${accountId}/substitute-products/${substituteProductId}/unlink-product/${productNodeId}`
  );
}
```

---

### Phase 4: Frontend Query Hooks

#### 4.1 Update or Create `useProducts` Hook
**File**: `frontend/src/queries/products.ts`

**Check if exists, if not create:**
```typescript
export const useProducts = (
  accountId: AccountId | null,
  categoryNodeId?: string | null,
  substituteProductNodeId?: string | null,  // NEW
) => {
  return useQuery({
    queryKey: accountId
      ? [...productsKeys.list(accountId), categoryNodeId, substituteProductNodeId]
      : (["products", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { products: [], total_count: 0 };
      return productService.list(accountId, categoryNodeId, substituteProductNodeId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5,
  });
};
```

---

#### 4.2 Create Link/Unlink Mutation Hooks
**File**: `frontend/src/queries/competitors.ts` (or products.ts)

```typescript
export const useLinkProductToSubstitute = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      substituteProductId: string;
      productNodeId: string;
    }) => substituteProductService.linkProduct(
      data.accountId,
      data.substituteProductId,
      data.productNodeId
    ),
    onSuccess: (_, variables) => {
      // Invalidate products list for this substitute
      queryClient.invalidateQueries({
        queryKey: productsKeys.list(variables.accountId),
      });
    },
  });
};

export const useUnlinkProductFromSubstitute = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      substituteProductId: string;
      productNodeId: string;
    }) => substituteProductService.unlinkProduct(
      data.accountId,
      data.substituteProductId,
      data.productNodeId
    ),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.list(variables.accountId),
      });
    },
  });
};
```

---

### Phase 5: Frontend Component Updates

#### 5.1 Load Products for Selected SubstituteProduct
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**Add after line 340:**
```typescript
// Products linked to selected SubstituteProduct (for React Flow)
const { data: linkedProductsData, isLoading: isLoadingLinkedProducts } =
  useProducts(
    mode === "substitute-products" && selectedChildId
      ? selectedOrgAccount?.accountId || null
      : null,
    undefined, // no category filter
    mode === "substitute-products" && selectedChildId
      ? selectedChildId  // SubstituteProduct node_id
      : null,
  );
const linkedProducts = linkedProductsData?.products || [];
```

---

#### 5.2 Update `generateNodes()` to Use Products Instead of ValuePropositions
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx:677-715`

**Replace current substitute-products branch:**
```typescript
} else if (mode === "substitute-products") {
  const substituteProduct = selectedChild as SubstituteProduct;

  nodes.push({
    id: substituteProduct.node_id,
    type: "substituteProductNode",
    position: {
      x: DIAGRAM_LAYOUT.PARENT_NODE_X,
      y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
    },
    data: {
      label: substituteProduct.product_name,
      isSelected: !selectedGrandchildId,
      onAddProduct: () => setIsLinkProductDialogOpen(true),  // NEW: Open link dialog
    },
  });

  const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
  const grandchildTotalWidth = linkedProducts.length * grandchildWidth - gap;
  const grandchildStartX = DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

  linkedProducts.forEach((product, index) => {
    nodes.push({
      id: product.node_id,
      type: "ourProductNode",  // Use existing OurProductNode from CompetitorFlowNodes
      position: {
        x: grandchildStartX + index * grandchildWidth,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
      },
      data: {
        label: product.product_name,
        showHandle: false,
        isSelected: selectedGrandchildId === product.node_id,
      },
    });
  });
}
```

---

#### 5.3 Update `generateEdges()` for Substitute Products
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx:750-761`

**Replace current branch:**
```typescript
} else if (mode === "substitute-products" && selectedChildId) {
  linkedProducts.forEach((product) => {
    edges.push({
      id: `${product.node_id}-${selectedChildId}`,
      source: product.node_id,
      target: selectedChildId,
      type: "smoothstep",
      style: DEFAULT_EDGE_STYLE,
      sourceHandle: "bottom",
      targetHandle: "top",
    });
  });
}
```

**Note**: Edge direction is `Product → SubstituteProduct` to match `MAY_BE_SUBSTITUTED_FOR` relationship

---

#### 5.4 Update `useMemo` Dependencies
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx:1533-1540`

**Update:**
```typescript
const nodes = useMemo(
  () => generateNodes(),
  [selectedChild, mode, risks, opportunities, linkedProducts, selectedGrandchildId],  // Replace valuePropositions with linkedProducts
);
const edges = useMemo(
  () => generateEdges(),
  [selectedChild, selectedChildId, mode, risks, opportunities, linkedProducts],  // Replace valuePropositions with linkedProducts
);
```

---

#### 5.5 Add Value Propositions to SubstituteProduct Side Sheet
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**Pattern**: Follow ProductCategoriesManagement.tsx:1435-1477

**Add after substitute product form fields in side sheet:**
```tsx
{contextMenuType === "child" && mode === "substitute-products" && (
  <SideSheetNestedList
    title="Value Propositions"
    tooltip="Reasons why customers might choose this substitute product over your offerings."
    items={valuePropositions}
    isLoading={isLoadingVPs}
    onAdd={() => setIsCreateVPModalOpen(true)}
    onEdit={(vp) => {
      setSelectedValueProposition(vp);
      setIsEditVPModalOpen(true);
    }}
    onDelete={(vp) => {
      setSelectedValueProposition(vp);
      setIsDeleteVPDialogOpen(true);
    }}
    hasEditAccess={hasEditAccess}
    isEditingParent={isEditing}
  />
)}
```

**State needed:**
- `isCreateVPModalOpen`, `isEditVPModalOpen`, `isDeleteVPDialogOpen`
- `selectedValueProposition`
- VP create/update/delete handlers

---

#### 5.6 Add Product Linking Dialog for React Flow Node Clicks
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**New State:**
```typescript
const [isLinkProductDialogOpen, setIsLinkProductDialogOpen] = useState(false);
const [selectedProductToLink, setSelectedProductToLink] = useState<Product | null>(null);
```

**New Dialog Component:**
```tsx
{/* Link Product to Substitute Product Dialog */}
<Dialog open={isLinkProductDialogOpen} onOpenChange={setIsLinkProductDialogOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Link Product to Substitute</DialogTitle>
      <DialogDescription>
        Select which of your products may be substituted by this competitor's offering.
      </DialogDescription>
    </DialogHeader>

    {/* Product Selector - Show ALL products in account */}
    <div className="space-y-4">
      <Label>Select Product</Label>
      <select
        value={selectedProductToLink?.node_id || ""}
        onChange={(e) => {
          const product = allProducts.find(p => p.node_id === e.target.value);
          setSelectedProductToLink(product || null);
        }}
      >
        <option value="">-- Select Product --</option>
        {allProducts.map(product => (
          <option key={product.node_id} value={product.node_id}>
            {product.product_name}
          </option>
        ))}
      </select>
    </div>

    <DialogFooter>
      <Button variant="outline" onClick={() => setIsLinkProductDialogOpen(false)}>
        Cancel
      </Button>
      <Button onClick={handleLinkProduct}>
        Link Product
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**Data needed:**
- Load ALL products in account (not filtered): `useProducts(accountId, null, null)`
- Store in `allProducts` variable

---

#### 5.7 Update `handleNodeClick` for Product Nodes
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx:767-825`

**Add case for ourProductNode:**
```typescript
// Product nodes (in substitute-products mode)
if (node.type === "ourProductNode" && mode === "substitute-products") {
  const product = linkedProducts.find((p) => p.node_id === node.id);
  if (product) {
    setSelectedGrandchild(product);
    setSelectedGrandchildId(product.node_id);
    // Open side sheet to allow unlinking
    setContextMenuType("grandchild");
    setIsContextMenuOpen(true);
  }
  return;
}

// SubstituteProduct node (parent in diagram)
if (node.type === "substituteProductNode" && mode === "substitute-products") {
  // Open side sheet for substitute product (shows VPs)
  if (selectedChild) {
    const subProduct = selectedChild as SubstituteProduct;
    setFormData({
      display_name: "",
      description: subProduct.description,
      product_name: subProduct.product_name,
      product_detail_page: subProduct.product_detail_page || "",
    });
    setContextMenuType("child");
    setIsContextMenuOpen(true);
  }
  return;
}
```

---

#### 5.8 Add Handler for Link/Unlink Actions
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**New handlers:**
```typescript
const handleLinkProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedChild || !selectedProductToLink) return;

  try {
    startOperation("Linking product...");

    await linkProductMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      substituteProductId: selectedChild.node_id,
      productNodeId: selectedProductToLink.node_id,
    });

    toast({
      title: "Success",
      description: "Product linked successfully",
    });

    setIsLinkProductDialogOpen(false);
    setSelectedProductToLink(null);
  } catch (error) {
    console.error("Failed to link product:", error);
    // Error handling...
  } finally {
    endOperation();
  }
};

const handleUnlinkProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedChild || !selectedGrandchild) return;

  try {
    startOperation("Unlinking product...");

    await unlinkProductMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      substituteProductId: selectedChild.node_id,
      productNodeId: selectedGrandchild.node_id,
    });

    toast({
      title: "Success",
      description: "Product unlinked successfully",
    });

    setIsContextMenuOpen(false);
  } catch (error) {
    console.error("Failed to unlink product:", error);
    // Error handling...
  } finally {
    endOperation();
  }
};
```

---

#### 5.9 Update Side Sheet for Product (Grandchild) in Substitute Mode
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**When `contextMenuType === "grandchild" && mode === "substitute-products"`:**
```tsx
<KnowledgeGraphSideSheet
  open={isContextMenuOpen && contextMenuType === "grandchild"}
  onOpenChange={setIsContextMenuOpen}
  title={(selectedGrandchild as Product)?.product_name || "Product"}
  icon={Package}
  isEditing={false}  // Read-only, no editing
  hasEditAccess={hasEditAccess}
  onDelete={handleUnlinkProduct}  // "Unlink" instead of "Delete"
>
  <div className="space-y-4">
    <div>
      <Label>Product Name</Label>
      <p className="text-sm text-muted-foreground">
        {(selectedGrandchild as Product)?.product_name}
      </p>
    </div>
    <div>
      <Label>Description</Label>
      <p className="text-sm text-muted-foreground">
        {(selectedGrandchild as Product)?.description}
      </p>
    </div>
    <p className="text-xs text-muted-foreground mt-4">
      This product may be substituted by the selected competitor offering.
      Click "Delete" to remove this relationship.
    </p>
  </div>
</KnowledgeGraphSideSheet>
```

**Button Label**: Change delete button to say "Unlink" instead of "Delete"

---

### Phase 6: UI Labels and Icons

#### 6.1 Update `grandchildrenLabel` Logic
**File**: `frontend/src/components/competitors/CompetitorsManagement.tsx`

**Add substitute-products case:**
```typescript
const grandchildrenLabel =
  mode === "strengths"
    ? "Risks"
    : mode === "weaknesses"
      ? "Opportunities"
      : "Products";  // NEW
```

---

#### 6.2 Update React Flow Visualization Card
**Already updated in current session** - just verify:
- Title uses `grandchildrenLabel` → will show "Products"
- Icon uses `Package` for substitute-products mode ✓
- Tooltip shows correct description ✓

---

### Phase 7: Testing Checklist

#### Backend Tests
- [ ] `list_products` with `substitute_product_node_id` parameter returns correct products
- [ ] Cannot filter by both `category_node_id` and `substitute_product_node_id`
- [ ] Link endpoint creates MAY_BE_SUBSTITUTED_FOR relationship
- [ ] Unlink endpoint removes relationship
- [ ] Linked products include category information (N+1 prevention)

#### Frontend Tests
- [ ] Selecting substitute product shows Product nodes in React Flow
- [ ] Clicking SubstituteProduct node opens side sheet with Value Propositions
- [ ] Clicking Product node opens side sheet with unlink option
- [ ] Clicking "+" on SubstituteProduct node opens link dialog
- [ ] Link dialog shows ALL products in account
- [ ] Linking a product adds node to React Flow immediately
- [ ] Unlinking a product removes node from React Flow immediately
- [ ] Value Propositions CRUD works in nested list

---

## Implementation Order (Multi-Session)

### Session 1: Backend Foundation
1. Update `list_products` endpoint with `substitute_product_node_id` filter
2. Update `list_products_with_categories` service method
3. Test with curl/Postman

### Session 2: Backend Relationships
1. Create link/unlink endpoints
2. Add service methods for relationship management
3. Test relationship CRUD

### Session 3: Frontend Service & Hooks
1. Update `productService.list()`
2. Update or create `useProducts` hook
3. Create `useLinkProductToSubstitute` and `useUnlinkProductFromSubstitute` hooks

### Session 4: Frontend UI Integration
1. Load linked products in CompetitorsManagement
2. Update `generateNodes()` and `generateEdges()`
3. Add link/unlink dialogs and handlers
4. Update side sheet for Product nodes
5. Add Value Propositions nested list to SubstituteProduct side sheet

### Session 5: Testing & Polish
1. Manual testing of full workflow
2. Fix any bugs discovered
3. Add integration tests
4. Update documentation

---

## Key Design Decisions

### Why Not Show ValuePropositions in React Flow?
- **Consistency**: Products page shows VPs in side sheet, not diagram
- **Clarity**: React Flow shows structural relationships (Product ↔ Substitute)
- **Usability**: VPs are metadata, not primary navigation structure

### Why Link Dialog Instead of Creating Products?
- **Data Integrity**: Products are primary business entities managed on /knowledge/products
- **Avoid Duplication**: Prevents orphaned or duplicate product records
- **Clear Ownership**: Product creation stays in one place

### Why Read-Only Product Side Sheet?
- **Single Source of Truth**: Product details edited on /knowledge/products page only
- **Focused Action**: Relationship management (link/unlink) is the only action needed
- **Prevents Confusion**: User knows where to go to edit product details

---

## Files to Modify

### Backend (4 files)
1. `api/src/kene_api/routers/knowledge_graph/business.py` - list_products endpoint
2. `api/src/kene_api/routers/knowledge_graph/competitive.py` - link/unlink endpoints (NEW or update existing)
3. `api/src/kene_api/services/graph_sync_service.py` - list_products_with_categories
4. `api/tests/integration/test_knowledge_graph_endpoints.py` - Add tests

### Frontend (4-5 files)
1. `frontend/src/services/productService.ts` - Update list() method
2. `frontend/src/services/substituteProductService.ts` - Add link/unlink methods
3. `frontend/src/queries/products.ts` - Update useProducts hook
4. `frontend/src/queries/competitors.ts` - Add link/unlink mutation hooks
5. `frontend/src/components/competitors/CompetitorsManagement.tsx` - Major UI updates

---

## Estimated Effort

- **Backend**: ~2-3 hours (straightforward query updates + new endpoints)
- **Frontend**: ~3-4 hours (component restructuring, new dialogs, state management)
- **Testing**: ~1-2 hours
- **Total**: ~6-9 hours across 3-5 sessions

---

## Design Decisions (CONFIRMED)

1. ✅ **Product Node Appearance**: Use EXACT same styling as /knowledge/products page (ProductNode component)

2. ✅ **Unlink Button Label**: Use "Unlink"

3. ✅ **Link Dialog UX**:
   - Show which products are already linked (disabled/grayed out in list)
   - Single-select dropdown (no multi-select)
   - No category grouping needed

4. ✅ **Empty State**: Show "No products linked yet" when SubstituteProduct has no linked products

5. ✅ **Value Proposition Implementation**: Copy EXACT implementation from /knowledge/products page side sheet
   - Use SideSheetNestedList component
   - Use separate modals for VP create/edit (match products page pattern)
   - Include same tooltips and descriptions

---

## Additional Implementation Details

### Value Propositions Pattern
**Reference**: `frontend/src/components/products/ProductCategoriesManagement.tsx:1435-1477`

- Use existing VP CRUD modals and handlers
- VPs are nested list in SubstituteProduct side sheet (NOT in React Flow)
- Clicking VP in list opens edit modal
- All VP state management follows products page pattern exactly

### Product Node Styling
**Reference**: `frontend/src/components/products/ProductFlowNodes.tsx`

- Import and use existing `ProductNode` component or `OurProductNode` from CompetitorFlowNodes
- Maintain consistent visual appearance across pages
- Package icon, blue color scheme

### Link Dialog Behavior
- Dropdown shows ALL products in account
- Already-linked products appear disabled/grayed in dropdown
- Single selection per action
- Immediate React Flow update after linking

---

## SESSION 1 COMPLETION STATUS ✅

### Completed Work (2025-11-18)

#### Backend (Phases 1-2) ✅
- [x] Updated `list_products` endpoint with `substitute_product_node_id` filter
- [x] Added validation to prevent filtering by both `category_node_id` and `substitute_product_node_id`
- [x] Updated `list_products_with_categories` service method with substitute product branch
- [x] Created `link_product_to_substitute` endpoint in `competitive.py`
- [x] Created `unlink_product_from_substitute` endpoint in `competitive.py`
- [x] Added `link_product_to_substitute` method to GraphSyncService
- [x] Added `unlink_product_from_substitute` method to GraphSyncService
- [x] Used `MERGE` for link (idempotent) and proper validation

**Files Modified:**
- `api/src/kene_api/routers/knowledge_graph/business.py` (lines 193-244)
- `api/src/kene_api/routers/knowledge_graph/competitive.py` (lines 10, 791-870)
- `api/src/kene_api/services/graph_sync_service.py` (lines 990-1095, 2425-2494)

#### Frontend Services & Hooks (Phase 3) ✅
- [x] Updated `productService.list()` to accept `substituteProductNodeId` parameter
- [x] Added `linkProduct` method to `substituteProductService`
- [x] Added `unlinkProduct` method to `substituteProductService`
- [x] Updated `productKeys` query key factory for substitute product filtering
- [x] Updated `useProducts` hook with substitute product logic
- [x] Created `useLinkProductToSubstitute` mutation hook
- [x] Created `useUnlinkProductFromSubstitute` mutation hook

**Files Modified:**
- `frontend/src/services/productService.ts` (lines 39-55)
- `frontend/src/services/substituteProductService.ts` (lines 82-101)
- `frontend/src/queries/products.ts` (lines 23-85)
- `frontend/src/queries/competitors.ts` (lines 464-518)

---

## SESSION 2: PHASE 4 - UI INTEGRATION (PENDING)

### Overview
This phase integrates Products into the CompetitorsManagement React Flow diagram when a SubstituteProduct is selected, replacing the current ValueProposition visualization.

### Key Design Decisions Recap
1. **Products shown in React Flow** (not ValuePropositions)
2. **ValuePropositions moved to SubstituteProduct side sheet** (nested list)
3. **Product nodes are read-only** with unlink functionality
4. **Link dialog** allows selecting from existing products (no creation)
5. **Edge direction**: `Product → SubstituteProduct` (matches `MAY_BE_SUBSTITUTED_FOR`)

---

## DETAILED IMPLEMENTATION GUIDE - PHASE 4

### File: `frontend/src/components/competitors/CompetitorsManagement.tsx`

---

### Step 1: Add Missing Imports

**Location**: Top of file (after line 88)

**Add:**
```typescript
import {
  useProducts,
  // ... other existing imports from @/queries/products
} from "@/queries/products";
import {
  useLinkProductToSubstitute,
  useUnlinkProductFromSubstitute,
  // ... other existing imports from @/queries/competitors
} from "@/queries/competitors";
import type { Product } from "@/services/productService";
```

**Check**: Verify these aren't already imported. The file already imports from these paths around lines 73-88.

---

### Step 2: Load Linked Products Data

**Location**: After line 341 (after `const valuePropositions = ...`)

**Add:**
```typescript
// Products linked to selected SubstituteProduct (for React Flow)
const { data: linkedProductsData, isLoading: isLoadingLinkedProducts } =
  useProducts(
    mode === "substitute-products" && selectedChildId
      ? selectedOrgAccount?.accountId || null
      : null,
    null, // No category filter
    mode === "substitute-products" && selectedChildId
      ? selectedChildId // SubstituteProduct node_id
      : null,
  );
const linkedProducts = linkedProductsData?.products || [];

// ALL products in account (for link dialog)
const { data: allProductsData, isLoading: isLoadingAllProducts } =
  useProducts(
    selectedOrgAccount?.accountId || null,
    null, // Will return empty - we need to modify this
    null,
  );
```

**Note**: The `useProducts` hook currently returns empty when both filters are null. We'll need to handle this by loading products differently for the link dialog. For now, we can work around this by loading products when the dialog opens.

---

### Step 3: Add Link/Unlink Mutation Hooks

**Location**: After the products data (after Step 2)

**Add:**
```typescript
// Link/Unlink mutations
const linkProductMutation = useLinkProductToSubstitute();
const unlinkProductMutation = useUnlinkProductFromSubstitute();
```

---

### Step 4: Add State for Link Dialog

**Location**: After line 346 (after VP form state)

**Add:**
```typescript
// Link product dialog state
const [isLinkProductDialogOpen, setIsLinkProductDialogOpen] = useState(false);
const [selectedProductToLink, setSelectedProductToLink] = useState<Product | null>(null);
const [linkDialogProducts, setLinkDialogProducts] = useState<Product[]>([]);
const [isLoadingLinkDialogProducts, setIsLoadingLinkDialogProducts] = useState(false);
```

---

### Step 5: Update `generateNodes()` Function

**Location**: Lines 678-717 (the `substitute-products` branch)

**Replace:**
```typescript
} else if (mode === "substitute-products") {
  const substituteProduct = selectedChild as SubstituteProduct;

  nodes.push({
    id: substituteProduct.node_id,
    type: "substituteProductNode",
    position: {
      x: DIAGRAM_LAYOUT.PARENT_NODE_X,
      y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
    },
    data: {
      label: substituteProduct.product_name,
      isSelected: !selectedGrandchildId,
      onAddValueProp: () => setIsCreateGrandchildModalOpen(true),
    },
  });

  const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
  const grandchildTotalWidth =
    valuePropositions.length * grandchildWidth - gap;
  const grandchildStartX =
    DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

  valuePropositions.forEach((vp, index) => {
    nodes.push({
      id: vp.node_id,
      type: "opportunityNode", // Reuse opportunity node styling for now
      position: {
        x: grandchildStartX + index * grandchildWidth,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
      },
      data: {
        label: vp.display_name,
        showHandle: false,
        isSelected: selectedGrandchildId === vp.node_id,
        onAddSubstitute: () => {},
      },
    });
  });
}
```

**With:**
```typescript
} else if (mode === "substitute-products") {
  const substituteProduct = selectedChild as SubstituteProduct;

  nodes.push({
    id: substituteProduct.node_id,
    type: "substituteProductNode",
    position: {
      x: DIAGRAM_LAYOUT.PARENT_NODE_X,
      y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
    },
    data: {
      label: substituteProduct.product_name,
      isSelected: !selectedGrandchildId,
      onAddProduct: () => handleOpenLinkDialog(), // NEW: Open link dialog
    },
  });

  const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
  const grandchildTotalWidth = linkedProducts.length * grandchildWidth - gap;
  const grandchildStartX = DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

  linkedProducts.forEach((product, index) => {
    nodes.push({
      id: product.node_id,
      type: "ourProductNode", // NEW: Use product node type
      position: {
        x: grandchildStartX + index * grandchildWidth,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
      },
      data: {
        label: product.product_name,
        showHandle: false,
        isSelected: selectedGrandchildId === product.node_id,
      },
    });
  });
}
```

**Key Changes:**
- Changed `onAddValueProp` to `onAddProduct` with new handler
- Changed from `valuePropositions` to `linkedProducts`
- Changed node type to `"ourProductNode"`
- Changed label to `product.product_name`

---

### Step 6: Update `generateEdges()` Function

**Location**: Lines 752-764 (the `substitute-products` branch)

**Replace:**
```typescript
} else if (mode === "substitute-products" && selectedChildId) {
  valuePropositions.forEach((vp) => {
    edges.push({
      id: `${selectedChildId}-${vp.node_id}`,
      source: selectedChildId,
      target: vp.node_id,
      type: "smoothstep",
      style: DEFAULT_EDGE_STYLE,
      sourceHandle: "bottom",
      targetHandle: "top",
    });
  });
}
```

**With:**
```typescript
} else if (mode === "substitute-products" && selectedChildId) {
  linkedProducts.forEach((product) => {
    edges.push({
      id: `${product.node_id}-${selectedChildId}`,
      source: product.node_id,
      target: selectedChildId,
      type: "smoothstep",
      style: DEFAULT_EDGE_STYLE,
      sourceHandle: "bottom",
      targetHandle: "top",
    });
  });
}
```

**Key Changes:**
- Changed from `valuePropositions` to `linkedProducts`
- **Reversed edge direction**: `Product → SubstituteProduct` (source is now product)
- Updated edge ID to match new direction

---

### Step 7: Update `handleNodeClick()` Function

**Location**: After line 814 (inside handleNodeClick function)

**Add (before the closing brace of handleNodeClick):**
```typescript
// Product nodes (in substitute-products mode)
if (node.type === "ourProductNode" && mode === "substitute-products") {
  const product = linkedProducts.find((p) => p.node_id === node.id);
  if (product) {
    setSelectedGrandchild(product as any); // Cast needed for type compatibility
    setSelectedGrandchildId(product.node_id);
    // Open side sheet to allow unlinking
    setContextMenuType("grandchild");
    setIsContextMenuOpen(true);
  }
  return;
}

// SubstituteProduct node (parent in diagram)
if (node.type === "substituteProductNode" && mode === "substitute-products") {
  // Open side sheet for substitute product (shows VPs)
  if (selectedChild) {
    const subProduct = selectedChild as SubstituteProduct;
    setFormData({
      display_name: subProduct.product_name,
      description: subProduct.description,
      product_name: subProduct.product_name,
      product_detail_page: subProduct.product_detail_page || "",
    } as any);
    setContextMenuType("child");
    setIsContextMenuOpen(true);
  }
  return;
}
```

---

### Step 8: Add Link Dialog Handler

**Location**: After handleNodeClick function (around line 820)

**Add:**
```typescript
// Handle opening link product dialog
const handleOpenLinkDialog = async () => {
  if (!selectedOrgAccount?.accountId) return;

  setIsLinkProductDialogOpen(true);
  setIsLoadingLinkDialogProducts(true);

  try {
    // Load ALL products in the account
    // We need to call the service directly since useProducts requires a filter
    const response = await productService.list(
      selectedOrgAccount.accountId,
      undefined, // No category filter
      undefined, // No substitute filter
      0,
      1000
    );

    // Filter out already linked products
    const linkedProductIds = new Set(linkedProducts.map(p => p.node_id));
    const availableProducts = response.products.filter(
      p => !linkedProductIds.has(p.node_id)
    );

    setLinkDialogProducts(availableProducts);
  } catch (error) {
    console.error("Failed to load products:", error);
    toast({
      title: "Error",
      description: "Failed to load products",
      variant: "destructive",
    });
  } finally {
    setIsLoadingLinkDialogProducts(false);
  }
};

// Handle linking product
const handleLinkProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedChild || !selectedProductToLink) return;

  try {
    startOperation("Linking product...");

    await linkProductMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      substituteProductId: selectedChild.node_id,
      productNodeId: selectedProductToLink.node_id,
    });

    toast({
      title: "Success",
      description: "Product linked successfully",
    });

    setIsLinkProductDialogOpen(false);
    setSelectedProductToLink(null);
  } catch (error) {
    console.error("Failed to link product:", error);
    toast({
      title: "Error",
      description: "Failed to link product",
      variant: "destructive",
    });
  } finally {
    endOperation();
  }
};

// Handle unlinking product
const handleUnlinkProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedChild || !selectedGrandchild) return;

  try {
    startOperation("Unlinking product...");

    await unlinkProductMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      substituteProductId: selectedChild.node_id,
      productNodeId: selectedGrandchild.node_id,
    });

    toast({
      title: "Success",
      description: "Product unlinked successfully",
    });

    setIsContextMenuOpen(false);
    setSelectedGrandchild(null);
    setSelectedGrandchildId(null);
  } catch (error) {
    console.error("Failed to unlink product:", error);
    toast({
      title: "Error",
      description: "Failed to unlink product",
      variant: "destructive",
    });
  } finally {
    endOperation();
  }
};
```

**Note**: You'll need to import `productService` at the top:
```typescript
import { productService } from "@/services/productService";
```

---

### Step 9: Update useMemo Dependencies

**Location**: Around line 1536-1544

**Find:**
```typescript
const nodes = useMemo(
  () => generateNodes(),
  [
    selectedChild,
    mode,
    risks,
    opportunities,
    valuePropositions,
    selectedGrandchildId,
  ],
);
```

**Replace with:**
```typescript
const nodes = useMemo(
  () => generateNodes(),
  [
    selectedChild,
    mode,
    risks,
    opportunities,
    linkedProducts, // CHANGED: from valuePropositions
    selectedGrandchildId,
  ],
);
```

**And find:**
```typescript
const edges = useMemo(
  () => generateEdges(),
  [selectedChild, selectedChildId, mode, risks, opportunities, valuePropositions],
);
```

**Replace with:**
```typescript
const edges = useMemo(
  () => generateEdges(),
  [selectedChild, selectedChildId, mode, risks, opportunities, linkedProducts], // CHANGED
);
```

---

### Step 10: Add Link Product Dialog Component

**Location**: In the JSX return section, after the existing modals (search for "Delete Grandchild Dialog" around line 2400+)

**Add:**
```tsx
{/* Link Product Dialog */}
<Dialog open={isLinkProductDialogOpen} onOpenChange={setIsLinkProductDialogOpen}>
  <DialogContent className="max-w-md">
    <DialogHeader>
      <DialogTitle>Link Product to Substitute</DialogTitle>
      <DialogDescription>
        Select which of your products may be substituted by this competitor's offering.
      </DialogDescription>
    </DialogHeader>

    <div className="space-y-4">
      {isLoadingLinkDialogProducts ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : linkDialogProducts.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No available products to link. All products are already linked or you have no products yet.
        </p>
      ) : (
        <>
          <Label>Select Product</Label>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={selectedProductToLink?.node_id || ""}
            onChange={(e) => {
              const product = linkDialogProducts.find(p => p.node_id === e.target.value);
              setSelectedProductToLink(product || null);
            }}
          >
            <option value="">-- Select Product --</option>
            {linkDialogProducts.map(product => (
              <option key={product.node_id} value={product.node_id}>
                {product.product_name}
              </option>
            ))}
          </select>
        </>
      )}
    </div>

    <DialogFooter>
      <Button
        variant="outline"
        onClick={() => {
          setIsLinkProductDialogOpen(false);
          setSelectedProductToLink(null);
        }}
      >
        Cancel
      </Button>
      <Button
        onClick={handleLinkProduct}
        disabled={!selectedProductToLink || linkProductMutation.isPending}
      >
        {linkProductMutation.isPending ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Linking...
          </>
        ) : (
          "Link Product"
        )}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

### Step 11: Update Product (Grandchild) Side Sheet for Substitute Mode

**Location**: Find the grandchild side sheet section (search for `contextMenuType === "grandchild"` around line 2200+)

**Find the section that handles grandchild side sheet and add a conditional for substitute-products mode:**

```tsx
{/* Grandchild Side Sheet - Products in Substitute Mode */}
{contextMenuType === "grandchild" && mode === "substitute-products" && (
  <KnowledgeGraphSideSheet
    open={isContextMenuOpen && contextMenuType === "grandchild"}
    onOpenChange={setIsContextMenuOpen}
    title={(selectedGrandchild as Product)?.product_name || "Product"}
    icon={Package}
    isEditing={false}
    hasEditAccess={hasEditAccess}
    onDelete={handleUnlinkProduct}
    deleteButtonLabel="Unlink"
  >
    <div className="space-y-4">
      <div>
        <Label>Product Name</Label>
        <p className="text-sm text-muted-foreground mt-1">
          {(selectedGrandchild as Product)?.product_name}
        </p>
      </div>
      <div>
        <Label>Description</Label>
        <p className="text-sm text-muted-foreground mt-1">
          {(selectedGrandchild as Product)?.description}
        </p>
      </div>
      {(selectedGrandchild as Product)?.product_detail_page && (
        <div>
          <Label>Product Page</Label>
          <a
            href={(selectedGrandchild as Product).product_detail_page}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline mt-1 block"
          >
            {(selectedGrandchild as Product).product_detail_page}
          </a>
        </div>
      )}
      <div className="rounded-md bg-muted p-3 mt-4">
        <p className="text-xs text-muted-foreground">
          This product may be substituted by the selected competitor offering.
          Click "Unlink" to remove this relationship.
        </p>
      </div>
    </div>
  </KnowledgeGraphSideSheet>
)}
```

---

### Step 12: Add ValuePropositions to SubstituteProduct Side Sheet

**Location**: Find the SubstituteProduct (child) side sheet (search for `mode === "substitute-products" && contextMenuType === "child"`)

**After the existing form fields in the side sheet, add:**

```tsx
{/* Value Propositions Nested List */}
{contextMenuType === "child" && mode === "substitute-products" && !isEditing && (
  <div className="mt-6 pt-6 border-t">
    <SideSheetNestedList
      title="Value Propositions"
      tooltip="Reasons why customers might choose this substitute product over your offerings."
      items={valuePropositions}
      isLoading={isLoadingVPs}
      onAdd={() => setIsCreateVPModalOpen(true)}
      onEdit={(vp) => {
        setSelectedValueProposition(vp);
        setValuePropositionFormData({
          display_name: vp.display_name,
          description: vp.description,
          parent_node_id: selectedChildId || "",
        });
        setIsEditVPModalOpen(true);
      }}
      onDelete={(vp) => {
        setSelectedValueProposition(vp);
        setIsDeleteVPDialogOpen(true);
      }}
      hasEditAccess={hasEditAccess}
      isEditingParent={isEditing}
    />
  </div>
)}
```

**Note**: Check if `SideSheetNestedList` component exists. If not, you may need to create it or use an alternative pattern. Look at the products page for reference.

---

### Step 13: Update grandchildrenLabel Logic

**Location**: Search for `grandchildrenLabel` (around line 1500+)

**Find:**
```typescript
const grandchildrenLabel =
  mode === "strengths"
    ? "Risks"
    : mode === "weaknesses"
      ? "Opportunities"
      : "Value Propositions";
```

**Replace with:**
```typescript
const grandchildrenLabel =
  mode === "strengths"
    ? "Risks"
    : mode === "weaknesses"
      ? "Opportunities"
      : "Products"; // CHANGED: from "Value Propositions"
```

---

## TESTING CHECKLIST

After implementing all changes:

### Backend Tests
- [ ] Test `GET /products?substitute_product_node_id=...` returns correct products
- [ ] Test filtering by both category and substitute returns 400 error
- [ ] Test `POST /substitute-products/{id}/link-product` creates relationship
- [ ] Test `DELETE /substitute-products/{id}/unlink-product/{product_id}` removes relationship
- [ ] Test linking same product twice is idempotent (no duplicate relationships)

### Frontend Tests (Manual)
- [ ] Select a SubstituteProduct - should show Product nodes in React Flow (not VPs)
- [ ] Click SubstituteProduct node - should open side sheet with Value Propositions nested list
- [ ] Click Product node - should open side sheet with unlink option
- [ ] Click "+" on SubstituteProduct node - should open link dialog
- [ ] Link dialog shows all available products (excluding already linked)
- [ ] Link dialog shows "No available products" when all are linked
- [ ] Linking a product adds node to React Flow immediately
- [ ] Unlinking a product removes node from React Flow immediately
- [ ] Value Propositions CRUD works in SubstituteProduct side sheet
- [ ] Edge direction is correct: Product → SubstituteProduct
- [ ] React Flow title shows "Products" (not "Value Propositions")
- [ ] Product node styling matches existing OurProductNode component

### Integration Tests
- [ ] Create SubstituteProduct → Link Product → Verify in database
- [ ] Link multiple products to same substitute
- [ ] Unlink product → Verify relationship removed in database
- [ ] Switch between competitors → Correct products shown
- [ ] Switch between substitute products → Correct products shown

---

## KNOWN ISSUES & WORKAROUNDS

### Issue 1: useProducts Hook Returns Empty Without Filters

**Problem**: The current `useProducts` hook returns empty when both `categoryId` and `substituteProductId` are null.

**Workaround**: In `handleOpenLinkDialog`, we call `productService.list()` directly instead of using the hook.

**Future Fix**: Consider adding an `allProducts` mode to the hook or creating a separate `useAllProducts` hook.

### Issue 2: Type Compatibility for selectedGrandchild

**Problem**: `selectedGrandchild` is typed as `Risk | Opportunity | null` but we're using `Product` in substitute mode.

**Workaround**: Use type casting `(selectedGrandchild as Product)` when in substitute mode.

**Future Fix**: Update the type definition to include `Product`:
```typescript
const [selectedGrandchild, setSelectedGrandchild] =
  useState<Risk | Opportunity | Product | null>(null);
```

### Issue 3: OurProductNode Component

**Assumption**: The implementation assumes an `ourProductNode` node type exists in `CompetitorFlowNodes.tsx`.

**Verification Needed**: Check if this component exists. If not, you may need to:
1. Create the component, OR
2. Reuse an existing node component (e.g., `opportunityNode` with different styling)

---

## FILE CHANGE SUMMARY

### Modified Files
1. `frontend/src/components/competitors/CompetitorsManagement.tsx` (Major changes)
   - Add imports
   - Add state for linked products and link dialog
   - Update `generateNodes()` function
   - Update `generateEdges()` function
   - Update `handleNodeClick()` function
   - Add link/unlink handlers
   - Add link dialog component
   - Update Product side sheet
   - Add VP nested list to SubstituteProduct side sheet
   - Update useMemo dependencies
   - Update grandchildrenLabel

### Estimated Lines Changed
- ~200-300 lines added/modified in CompetitorsManagement.tsx

---

## NEXT SESSION PREP

Before starting Session 2:
1. Review this implementation plan thoroughly
2. Ensure backend changes from Session 1 are deployed/tested
3. Have the CompetitorsManagement.tsx file open
4. Consider running type checking after each major step
5. Test incrementally - don't wait until all changes are done

**Recommended Approach**: Implement steps 1-7 first (data + React Flow), test, then add steps 8-13 (dialogs + side sheets).

---

## Ready for Session 2

All Session 1 work complete. Phase 4 implementation guide ready for next session.
