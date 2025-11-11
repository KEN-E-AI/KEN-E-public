# Product Network Diagram Implementation Plan

## Overview
Implement a React Flow network diagram in the Products card showing the hierarchy:
ProductCategory → Product → Substitute Product (placeholder)

## Reference Design
See attached screenshot showing:
- Light blue category node at top (Business Banking)
- Medium blue product nodes in middle row (Loans, Mortgages)
- Coral/pink substitute nodes at bottom (Truist Mortgages, Rocket Mortgage)
- Black straight edges connecting nodes
- "+" handles on nodes for creating children

## Current State
- ✅ ProductCategoriesManagement component with horizontal scrollable list
- ✅ About card showing selected category details with inline editing
- ✅ Products card placeholder (600px height, fills width)
- ✅ ReactFlow v11.11.4 installed and verified
- ✅ Codebase analysis complete - patterns identified

## Design Decisions (Finalized)

### Visual Design
- **Node sizing**: Match exact badge design from horizontal scroll (72px circles, 48px icons)
- **Colors**:
  - Category: `bg-brand-light-blue` (#8DC4F9)
  - Product: `bg-brand-medium-blue` (#468FD0)
  - Substitute: `bg-brand-dark-blue` (#163354)
- **Typography**: Exactly match existing category badges
- **Selection**: NO selection ring - use About card update + show "+" handle instead
- **"+" Handles**: Use React Flow built-in Handle components with custom styling positioned absolutely

### Interaction Behavior
- **Product click**: Immediately update About card (replace category info)
- **Category node click**: Restore category info in About card
- **"+" on category**: Open create product modal
- **"+" on product**: Open create substitute product modal (toast for now)
- **NO hover states** on "+" buttons
- **Initial state**: No product selected on load, no selection maintained on refresh

### Layout Behavior
- **Vertical spacing**: As specified in plan (y: 224 for products)
- **Horizontal spacing**: Measure actual badge width for proper centering
- **Canvas interaction**: Pan by dragging background, zoom with controls (not scroll-to-zoom)
- **Substitute products**: Centered under parent product

### Empty States
- **No products**: Show category node + "+" handle, empty space below
- **Loading**: Show Loader2 spinner
- **API error**: Show error message in card

### Post-Creation Behavior
- **After creating product**: Auto-select new product, show in About card, refresh diagram

## Codebase Consistency Analysis (COMPLETED)

### ✅ Patterns to Follow

1. **Service Layer Pattern**
   - Use class-based singleton like `productCategoryService.ts`
   - Define types IN the service file (not in types/knowledge.ts)
   - Export interfaces and service instance

2. **Type Organization**
   - Keep `Product`, `ProductCreate`, `ProductUpdate` in service file
   - Use `import type { ... }` for type-only imports (BP C-6)
   - Optional: Add branded types later (BP C-5)

3. **React Flow Import Pattern**
   - Match ChannelControls.tsx pattern (lines 1-13)
   - Import: ReactFlow, Node, Edge, Controls, Background, Handle, Position
   - CSS: `import 'reactflow/dist/style.css'`

4. **Component Organization**
   - Colocate CategoryNode + ProductNode in single file
   - Keep main logic in ProductCategoriesManagement.tsx
   - Use pure functions for node/edge generation (BP C-3)

5. **Best Practices Compliance**
   - BP-1: ✅ Asked clarifying questions
   - C-2: ✅ Use existing domain vocabulary
   - C-3: ✅ Functions not classes for node generation
   - C-6: ✅ Use `import type` for type-only imports
   - O-1: ✅ Keep code in correct directories
   - O-3: ✅ Reusable service in services/

## Implementation Phases

### Phase 0: Product Service Layer (NEW FIRST STEP)

**File:** `frontend/src/services/productService.ts`

Following exact pattern of `productCategoryService.ts`:

```typescript
import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Product {
  node_id: string;
  account_id: string;
  product_name: string;
  description: string;
  references: string[];
  product_detail_page?: string;
  category_node_id: string;
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface ProductCreate {
  product_name: string;
  description: string;
  category_node_id: string;
  references?: string[];
  product_detail_page?: string;
}

export interface ProductUpdate {
  product_name?: string;
  description?: string;
  references?: string[];
  product_detail_page?: string;
}

interface ProductListResponse {
  products: Product[];
  total_count: number;
}

class ProductService {
  async list(
    accountId: AccountId,
    categoryNodeId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<ProductListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/products`,
      { params: { category_node_id: categoryNodeId, skip, limit } },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: ProductCreate,
  ): Promise<Product> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/products`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: ProductUpdate,
  ): Promise<Product> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/products/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/products/${nodeId}`,
    );
  }
}

export const productService = new ProductService();
```

### Phase 1: Add Product State to ProductCategoriesManagement

**File:** `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Import Changes:**
```typescript
import type { Product } from "@/services/productService";
import { productService } from "@/services/productService";
```

**State Additions:**
```typescript
const [products, setProducts] = useState<Product[]>([]);
const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
const [isLoadingProducts, setIsLoadingProducts] = useState(false);
const [isCreateProductModalOpen, setIsCreateProductModalOpen] = useState(false);
const [productFormData, setProductFormData] = useState<ProductCreate>({
  product_name: "",
  description: "",
  category_node_id: "",
  references: [],
  product_detail_page: "",
});
```

**Fetch Function:**
```typescript
const fetchProducts = async (categoryNodeId: string) => {
  if (!selectedOrgAccount?.accountId) return;

  try {
    setIsLoadingProducts(true);
    const response = await productService.list(
      selectedOrgAccount.accountId,
      categoryNodeId,
    );
    setProducts(response.products);
  } catch (error) {
    console.error("Failed to load products:", error);
    toast({
      title: "Error",
      description: "Failed to load products",
      variant: "destructive",
    });
  } finally {
    setIsLoadingProducts(false);
  }
};
```

**useEffect:**
```typescript
useEffect(() => {
  if (selectedCategoryId) {
    fetchProducts(selectedCategoryId);
  } else {
    setProducts([]);
    setSelectedProductId(null);
    setSelectedProduct(null);
  }
}, [selectedCategoryId, selectedOrgAccount]);
```

### Phase 2: Custom React Flow Nodes

**File:** `frontend/src/components/products/ProductFlowNodes.tsx` (NEW)

**Imports (following ChannelControls pattern):**
```typescript
import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { Plus, Blocks, Package } from "lucide-react";
```

**CategoryNode Component:**
```typescript
interface CategoryNodeData {
  label: string; // product_name
  onAddProduct: () => void;
}

export const CategoryNode = memo(({ data }: NodeProps<CategoryNodeData>) => {
  return (
    <div className="relative">
      {/* Badge matching horizontal scroll design */}
      <div className="flex items-center">
        {/* Text Box - Left */}
        <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
          <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
            Product Category
          </p>
          <p className="font-semibold text-dashboard-gray-900 leading-tight">
            {data.label}
          </p>
        </div>

        {/* Circle with Icon - Right */}
        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-light-blue flex items-center justify-center"
            style={{ width: "72px", height: "72px" }}
          >
            <Blocks
              className="text-white"
              style={{ width: "48px", height: "48px" }}
            />
          </div>
        </div>
      </div>

      {/* React Flow Handle (invisible) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        className="opacity-0"
      />

      {/* Custom "+" Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          data.onAddProduct();
        }}
        className="absolute -bottom-[17px] left-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-brand-light-blue flex items-center justify-center z-20"
      >
        <Plus className="h-4 w-4 text-white" />
      </button>
    </div>
  );
});

CategoryNode.displayName = "CategoryNode";
```

**ProductNode Component:**
```typescript
interface ProductNodeData {
  label: string; // product_name
  showHandle: boolean;
  isSelected: boolean;
  onAddSubstitute: () => void;
}

export const ProductNode = memo(({ data }: NodeProps<ProductNodeData>) => {
  return (
    <div className="relative">
      {/* Badge matching horizontal scroll design */}
      <div className="flex items-center">
        {/* Text Box - Left */}
        <div className="bg-brand-medium-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
          <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
            Product:
          </p>
          <p className="font-semibold text-dashboard-gray-900 leading-tight">
            {data.label}
          </p>
        </div>

        {/* Circle with Icon - Right */}
        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-medium-blue flex items-center justify-center"
            style={{ width: "72px", height: "72px" }}
          >
            <Package
              className="text-white"
              style={{ width: "48px", height: "48px" }}
            />
          </div>
        </div>
      </div>

      {/* Top Handle for incoming connections */}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="opacity-0"
      />

      {/* Bottom Handle for outgoing connections (when selected) */}
      {data.showHandle && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="bottom"
            className="opacity-0"
          />

          {/* Custom "+" Button (only when showHandle is true) */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              data.onAddSubstitute();
            }}
            className="absolute -bottom-[17px] left-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-brand-medium-blue flex items-center justify-center z-20"
          >
            <Plus className="h-4 w-4 text-white" />
          </button>
        </>
      )}
    </div>
  );
});

ProductNode.displayName = "ProductNode";
```

### Phase 3: Node & Edge Generation

**File:** `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Generate Nodes Function:**
```typescript
const generateNodes = (): Node[] => {
  if (!selectedCategory) return [];

  const nodes: Node[] = [];

  // Category Node (top center)
  nodes.push({
    id: selectedCategory.node_id,
    type: 'categoryNode',
    position: { x: 300, y: 50 },
    data: {
      label: selectedCategory.product_name,
      onAddProduct: () => setIsCreateProductModalOpen(true),
    },
  });

  // Product Nodes (row below, horizontally spaced)
  // Measure actual badge width for proper centering
  const productWidth = 300; // Approximate - adjust based on actual rendering
  const gap = 12;
  const totalWidth = products.length * (productWidth + gap) - gap;
  const startX = 300 - (totalWidth / 2);

  products.forEach((product, index) => {
    nodes.push({
      id: product.node_id,
      type: 'productNode',
      position: {
        x: startX + (index * (productWidth + gap)),
        y: 224, // 50 + 150 (badge) + 24 (vertical spacing)
      },
      data: {
        label: product.product_name,
        showHandle: selectedProductId === product.node_id,
        isSelected: selectedProductId === product.node_id,
        onAddSubstitute: () => {
          toast({
            title: "Coming Soon",
            description: "Substitute products API not yet available",
          });
        },
      },
    });
  });

  return nodes;
};
```

**Generate Edges Function:**
```typescript
const generateEdges = (): Edge[] => {
  if (!selectedCategory) return [];

  const edges: Edge[] = [];

  // Connect category to each product
  products.forEach((product) => {
    edges.push({
      id: `${selectedCategory.node_id}-${product.node_id}`,
      source: selectedCategory.node_id,
      target: product.node_id,
      type: 'straight',
      style: {
        stroke: '#000',
        strokeWidth: 2,
      },
      sourceHandle: 'bottom',
      targetHandle: 'top',
    });
  });

  return edges;
};
```

### Phase 4: React Flow Integration

**File:** `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Imports (following ChannelControls pattern):**
```typescript
import {
  ReactFlow,
  Controls,
  Background,
} from "reactflow";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import { CategoryNode, ProductNode } from "./ProductFlowNodes";
import { Loader2 } from "lucide-react"; // Add if not already imported
```

**Node Types Definition:**
```typescript
const nodeTypes = {
  categoryNode: CategoryNode,
  productNode: ProductNode,
};
```

**Handle Node Click:**
```typescript
const handleProductNodeClick = (_event: React.MouseEvent, node: Node) => {
  if (node.type === 'productNode') {
    // Find the product
    const product = products.find(p => p.node_id === node.id);
    if (!product) return;

    // Update selection
    setSelectedProductId(node.id);
    setSelectedProduct(product);

    // Clear category selection to show product in About card
    setSelectedCategory(null);
    setSelectedCategoryId(null);

    // Update form data for About card
    setFormData({
      product_name: product.product_name,
      description: product.description,
    });

    setIsEditing(false);
  } else if (node.type === 'categoryNode') {
    // Restore category in About card
    const category = categories.find(c => c.node_id === node.id);
    if (!category) return;

    setSelectedCategoryId(category.node_id);
    setSelectedCategory(category);
    setSelectedProductId(null);
    setSelectedProduct(null);

    setFormData({
      product_name: category.product_name,
      description: category.description,
    });

    setIsEditing(false);
  }
};
```

**Products Card Content (replace placeholder):**
```tsx
{/* Products Card - Only show when category is selected */}
{selectedCategoryId && (
  <Card className="flex-1 h-[600px]">
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <Package className="h-5 w-5" />
        Products
      </CardTitle>
    </CardHeader>
    <CardContent className="h-[520px]">
      {isLoadingProducts ? (
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : (
        <ReactFlow
          nodes={generateNodes()}
          edges={generateEdges()}
          nodeTypes={nodeTypes}
          onNodeClick={handleProductNodeClick}
          fitView
          minZoom={0.5}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={true}
          panOnScroll={true}
          zoomOnScroll={false}
        >
          <Background />
          <Controls />
        </ReactFlow>
      )}
    </CardContent>
  </Card>
)}
```

### Phase 5: About Card Updates for Product Display

**File:** `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Update About Card Logic:**

The About card needs to display either a category OR a product. Update the conditional rendering:

```tsx
{/* About Section - Show when category OR product is selected */}
<div className="flex gap-6 mt-6">
  {(selectedCategory || selectedProduct) ? (
    <Card className="w-[400px]">
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="flex items-center gap-2">
            About
            {hasEditAccess && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="text-dashboard-gray-600 hover:text-dashboard-gray-900"
              >
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </CardTitle>
          {hasEditAccess && !isEditing && (
            <button
              onClick={() => {
                if (selectedCategory) {
                  handleDeleteClick(selectedCategory);
                } else if (selectedProduct) {
                  handleDeleteProductClick(selectedProduct);
                }
              }}
              className="text-brand-red hover:text-brand-red/80"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isEditing ? (
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-name">Name:</Label>
              <Input
                id="edit-name"
                value={formData.product_name}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    product_name: e.target.value,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="edit-description">Description:</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    description: e.target.value,
                  })
                }
                rows={4}
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  setIsEditing(false);
                  if (selectedCategory) {
                    setFormData({
                      product_name: selectedCategory.product_name,
                      description: selectedCategory.description,
                    });
                  } else if (selectedProduct) {
                    setFormData({
                      product_name: selectedProduct.product_name,
                      description: selectedProduct.description,
                    });
                  }
                }}
                variant="outline"
              >
                Cancel
              </Button>
              <Button onClick={selectedCategory ? handleSave : handleProductSave}>
                Save Changes
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <p className="font-semibold">Type:</p>
              <p>{selectedCategory ? "Product Category" : "Product"}</p>
            </div>
            <div>
              <p className="font-semibold">Name:</p>
              <p>
                {selectedCategory?.product_name || selectedProduct?.product_name}
              </p>
            </div>
            <div>
              <p className="font-semibold">Description:</p>
              <p className="text-sm text-dashboard-gray-600">
                {selectedCategory?.description ||
                  selectedProduct?.description ||
                  "No description provided"}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  ) : (
    <div className="p-6 bg-dashboard-gray-50 rounded-lg border border-dashboard-gray-200">
      <p className="text-dashboard-gray-500 text-center">
        Select a product category to view details.
      </p>
    </div>
  )}

  {/* Products Card stays the same */}
</div>
```

### Phase 6: Create Product Modal

**File:** `frontend/src/components/products/ProductCategoriesManagement.tsx`

**Modal Component:**
```tsx
{/* Create Product Modal */}
<Dialog open={isCreateProductModalOpen} onOpenChange={setIsCreateProductModalOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Create Product</DialogTitle>
      <DialogDescription>
        Add a new product to {selectedCategory?.product_name}
      </DialogDescription>
    </DialogHeader>
    <div className="space-y-4 pt-4">
      <div>
        <Label htmlFor="create-product-name">Product Name *</Label>
        <Input
          id="create-product-name"
          value={productFormData.product_name}
          onChange={(e) =>
            setProductFormData({
              ...productFormData,
              product_name: e.target.value,
            })
          }
          placeholder="e.g., Business Loans"
          maxLength={200}
        />
      </div>
      <div>
        <Label htmlFor="create-product-description">Description *</Label>
        <Textarea
          id="create-product-description"
          value={productFormData.description}
          onChange={(e) =>
            setProductFormData({
              ...productFormData,
              description: e.target.value,
            })
          }
          placeholder="Describe this product..."
          rows={4}
          maxLength={4000}
        />
      </div>
      <div>
        <Label htmlFor="create-product-detail-page">Product Detail Page (Optional)</Label>
        <Input
          id="create-product-detail-page"
          type="url"
          value={productFormData.product_detail_page}
          onChange={(e) =>
            setProductFormData({
              ...productFormData,
              product_detail_page: e.target.value,
            })
          }
          placeholder="https://..."
        />
      </div>
      <div>
        <Label htmlFor="create-product-references">References (Optional)</Label>
        <Textarea
          id="create-product-references"
          value={productFormData.references?.join("\n") || ""}
          onChange={(e) => {
            const refs = e.target.value.split("\n").filter(r => r.trim());
            setProductFormData({
              ...productFormData,
              references: refs,
            });
          }}
          placeholder="One URL per line"
          rows={3}
        />
      </div>
    </div>
    <DialogFooter>
      <Button
        variant="outline"
        onClick={() => {
          setIsCreateProductModalOpen(false);
          setProductFormData({
            product_name: "",
            description: "",
            category_node_id: "",
            references: [],
            product_detail_page: "",
          });
        }}
      >
        Cancel
      </Button>
      <Button
        onClick={handleCreateProduct}
        disabled={
          !productFormData.product_name.trim() ||
          !productFormData.description.trim()
        }
      >
        Create Product
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**Create Product Handler:**
```typescript
const handleCreateProduct = async () => {
  if (!selectedOrgAccount?.accountId || !selectedCategory) return;
  if (!productFormData.product_name.trim() || !productFormData.description.trim()) {
    toast({
      title: "Validation Error",
      description: "Product name and description are required",
      variant: "destructive",
    });
    return;
  }

  try {
    startOperation("Creating product...");
    setIsCreateProductModalOpen(false);

    const productData: ProductCreate = {
      product_name: productFormData.product_name,
      description: productFormData.description,
      category_node_id: selectedCategory.node_id,
      references: productFormData.references?.filter(r => r.trim()) || [],
      product_detail_page: productFormData.product_detail_page?.trim() || undefined,
    };

    const newProduct = await productService.create(
      selectedOrgAccount.accountId,
      productData,
    );

    // Refresh products list
    await fetchProducts(selectedCategory.node_id);

    // Auto-select new product
    setSelectedProductId(newProduct.node_id);
    setSelectedProduct(newProduct);
    setSelectedCategory(null);
    setSelectedCategoryId(null);

    // Update About card
    setFormData({
      product_name: newProduct.product_name,
      description: newProduct.description,
    });

    // Reset form
    setProductFormData({
      product_name: "",
      description: "",
      category_node_id: "",
      references: [],
      product_detail_page: "",
    });

    toast({
      title: "Success",
      description: "Product created successfully",
    });
  } catch (error) {
    console.error("Failed to create product:", error);

    if (axios.isAxiosError(error)) {
      const status = error.response?.status;
      const message = error.response?.data?.detail || "Failed to create product";

      if (status === 409) {
        toast({
          title: "Duplicate Product",
          description: "A product with this name already exists in this category",
          variant: "destructive",
        });
      } else if (status === 403) {
        toast({
          title: "Permission Denied",
          description: "You don't have permission to create products",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      }
    }
  } finally {
    endOperation();
  }
};
```

**Product Delete Handler (placeholder for About card):**
```typescript
const handleDeleteProductClick = (product: Product) => {
  // TODO: Implement in future session
  toast({
    title: "Coming Soon",
    description: "Product deletion will be implemented in a future session",
  });
};

const handleProductSave = async () => {
  // TODO: Implement in future session
  toast({
    title: "Coming Soon",
    description: "Product editing will be implemented in a future session",
  });
};
```

## Advanced Features for Future Sessions

### Not Implementing Now (Placeholder/Plan Only):

1. **Substitute Products (Level 3)**
   - Needs new API endpoint: `/api/v1/knowledge-graph/{account_id}/substitute-products`
   - Will appear below selected product (centered)
   - Styling: `bg-brand-dark-blue` (#163354)
   - Create substitute product modal when clicking "+" on product node
   - Similar structure to product nodes

2. **Product Edit/Delete from About Card**
   - `handleProductSave` function (update via productService)
   - `handleDeleteProductClick` function (delete via productService)
   - Add delete confirmation dialog for products
   - Refresh diagram after delete
   - Clear selection after delete

3. **Advanced Layout**
   - Handle many products (horizontal overflow scrolling in canvas)
   - Substitute product positioning algorithm (multiple under one parent)
   - Dynamic sizing based on content
   - Responsive node positioning

4. **Product Node Details**
   - Show `references` in About card
   - Show `product_detail_page` as clickable link
   - Show created_by, last_modified_by timestamps
   - Link to product detail page

5. **Filtering & Search**
   - Search products by name
   - Filter by attributes
   - Collapse/expand branches

## Files to Create/Modify

### Phase 0: Service Layer
1. ✅ Verify reactflow installation
2. 📝 `frontend/src/services/productService.ts` - **NEW** (create first)

### Phase 1: State Management
3. 📝 `frontend/src/components/products/ProductCategoriesManagement.tsx` - MODIFY
   - Add product state
   - Add fetchProducts function
   - Add useEffect for product loading

### Phase 2: Custom Nodes
4. 📝 `frontend/src/components/products/ProductFlowNodes.tsx` - **NEW**
   - CategoryNode component
   - ProductNode component

### Phase 3-4: Integration
5. 📝 `frontend/src/components/products/ProductCategoriesManagement.tsx` - MODIFY
   - Add React Flow imports
   - Add node/edge generators
   - Replace Products card content with ReactFlow
   - Add node click handler

### Phase 5: About Card
6. 📝 `frontend/src/components/products/ProductCategoriesManagement.tsx` - MODIFY
   - Update About card conditional logic
   - Support both category and product display
   - Add placeholder edit/delete handlers for products

### Phase 6: Create Modal
7. 📝 `frontend/src/components/products/ProductCategoriesManagement.tsx` - MODIFY
   - Add Create Product modal
   - Add handleCreateProduct function
   - Wire up modal to category node "+" button

## Success Criteria - This Session

### Must Have (MVP)
- ✅ `productService.ts` created following exact pattern of `productCategoryService.ts`
- ✅ React Flow renders in Products card when category selected
- ✅ Category node appears at top with correct styling
- ✅ Product nodes appear below category with correct styling
- ✅ Edges connect category to products (black, 2px, straight)
- ✅ "+" handle visible on category node (always)
- ✅ "+" handle visible on selected product node (conditional)
- ✅ Products fetch from API when category selected
- ✅ Clicking product node updates About card
- ✅ Clicking category node restores category in About card
- ✅ Create Product modal works and creates products
- ✅ New products auto-select and show in About card
- ✅ Loading state shows spinner
- ✅ Empty state shows category + "+" handle only

### Nice to Have (Stretch Goals)
- ⏭️ Measure actual badge width for perfect centering
- ⏭️ Product edit functionality in About card
- ⏭️ Product delete functionality in About card
- ⏭️ Better error handling for API failures
- ⏭️ Branded types for node IDs

## Testing Checklist

### Manual Testing Steps
1. ✅ Select a category - Products card should appear with React Flow
2. ✅ Empty category - Should show category node + "+" handle only
3. ✅ Click "+" on category - Should open Create Product modal
4. ✅ Create product - Should auto-select and show in About card
5. ✅ Click product node - Should update About card immediately
6. ✅ Click category node in diagram - Should restore category in About
7. ✅ Click "+" on selected product - Should show "Coming Soon" toast
8. ✅ Pan canvas - Should work by dragging background
9. ✅ Zoom controls - Should zoom in/out with controls
10. ✅ Multiple products - Should layout horizontally with proper spacing
11. ✅ Loading state - Should show spinner while fetching
12. ✅ API error - Should show error toast

### Edge Cases to Test
- Category with 0 products
- Category with 1 product
- Category with 5+ products (test horizontal layout)
- Network error when fetching products
- Network error when creating product
- Validation: empty product name
- Validation: empty description
- Long product names (test text truncation)
- Switching between categories quickly

## Known Limitations

1. **Node positioning**: Using approximate badge width (300px) - may need adjustment
2. **No substitute products**: API not available yet, placeholder toast only
3. **No product edit/delete**: Placeholders in place, implement in future session
4. **No dynamic layout**: Fixed positioning, may need improvement for many nodes
5. **No branded types**: Using plain strings for IDs (can add later)

## Token Budget Check
Current: ~54K / 1M tokens used
Remaining: ~946K tokens

Ready to implement!
