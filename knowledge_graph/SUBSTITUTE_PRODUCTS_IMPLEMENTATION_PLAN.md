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

## Ready for Implementation

All design questions answered. Plan is complete and ready for multi-session implementation.

**Start with Session 1: Backend Foundation** when ready.
