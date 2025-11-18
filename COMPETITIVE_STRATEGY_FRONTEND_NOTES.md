# Competitive Strategy Frontend Implementation Notes

**Date:** 2025-01-18
**Purpose:** Document backend data model, API endpoints, and frontend patterns for building `/knowledge/competitors` pages

---

## Overview

The competitive strategist agent has gathered competitive intelligence data that is stored in Neo4j. This data needs to be displayed in the frontend under `/knowledge/competitors` (similar to how `/knowledge/account` and `/knowledge/products` work).

---

## Backend Data Model (Neo4j)

### Node Types & Relationships

The competitive strategy uses **6 node types** structured as follows:

```
Account
  └── CompetitiveEnvironment (hub node, auto-created)
       └── Competitor (1-10 competitors)
            ├── CompetitorTactic (1-5 marketing tactics per competitor)
            ├── CompetitorStrength (1-10 strengths per competitor)
            │    └── Risk (1-5 risks created by each strength)
            ├── CompetitorWeakness (1-10 weaknesses per competitor)
            │    └── Opportunity (1-5 opportunities created by each weakness)
            ├── ValueProposition (1-5 value props per competitor)
            └── SubstituteProduct (1-5 substitute products per competitor)
                 └── ValueProposition (1 value prop per substitute product)
```

### Key Implementation Notes

1. **Dual Labels**: All competitive nodes have TWO labels:
   - Specific type (e.g., `Competitor`, `SubstituteProduct`)
   - Generic `Strategy` label (for embedding search)

2. **Hub Pattern**: `CompetitiveEnvironment` is automatically created/reused as central hub (similar to `SWOTAnalysis` for business strategy)

3. **SWOT Pattern**:
   - `CompetitorStrength -[:CREATES]-> Risk` (risks for OUR company)
   - `CompetitorWeakness -[:CREATES]-> Opportunity` (opportunities for OUR company)

4. **Shared Nodes**: `Risk`, `Opportunity`, and `ValueProposition` are shared with business strategy

5. **References Field**: All nodes support `references: string[]` for source URLs

---

## Backend API Endpoints

Base path: `/api/v1/knowledge-graph/{account_id}/`

### CompetitiveEnvironment (Hub Node)
- `GET /competitive-environment` - Get the hub (auto-created with first competitor)
- `PATCH /competitive-environment` - Update hub description

### Competitors
- `POST /competitors` - Create competitor
- `GET /competitors` - List all competitors (with pagination)
- `GET /competitors/{node_id}` - Get specific competitor
- `PATCH /competitors/{node_id}` - Update competitor
- `DELETE /competitors/{node_id}` - Delete competitor

### CompetitorTactic
- `POST /competitor-tactics` - Create tactic
- `GET /competitor-tactics?skip=0&limit=1000` - List tactics
- `GET /competitor-tactics/{node_id}` - Get specific tactic
- `PATCH /competitor-tactics/{node_id}` - Update tactic
- `DELETE /competitor-tactics/{node_id}` - Delete tactic

### CompetitorStrength
- `POST /competitor-strengths` - Create strength
- `GET /competitor-strengths?skip=0&limit=1000` - List strengths
- `GET /competitor-strengths/{node_id}` - Get specific strength
- `PATCH /competitor-strengths/{node_id}` - Update strength
- `DELETE /competitor-strengths/{node_id}` - Delete strength

### CompetitorWeakness
- `POST /competitor-weaknesses` - Create weakness
- `GET /competitor-weaknesses?skip=0&limit=1000` - List weaknesses
- `GET /competitor-weaknesses/{node_id}` - Get specific weakness
- `PATCH /competitor-weaknesses/{node_id}` - Update weakness
- `DELETE /competitor-weaknesses/{node_id}` - Delete weakness

### SubstituteProduct
- `POST /substitute-products` - Create substitute product
- `GET /substitute-products?skip=0&limit=1000` - List substitute products
- `GET /substitute-products/{node_id}` - Get specific substitute product
- `PATCH /substitute-products/{node_id}` - Update substitute product
- `DELETE /substitute-products/{node_id}` - Delete substitute product

**Note:** Risk and Opportunity nodes are managed through existing business strategy endpoints (shared nodes)

---

## Pydantic Models (TypeScript Equivalents)

### CompetitiveEnvironment
```typescript
interface CompetitiveEnvironment {
  node_id: string;
  account_id: string;
  description: string;  // Strategy for identifying competitors
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

### Competitor
```typescript
interface Competitor {
  node_id: string;
  account_id: string;
  display_name: string;  // max 200 chars
  description: string;   // max 4000 chars - company summary
  references: string[];  // Source URLs
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

### CompetitorTactic
```typescript
interface CompetitorTactic {
  node_id: string;
  account_id: string;
  display_name: string;        // max 200 chars
  description: string;         // max 4000 chars
  references: string[];
  competitor_node_id: string;  // Parent competitor
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

### CompetitorStrength
```typescript
interface CompetitorStrength {
  node_id: string;
  account_id: string;
  display_name: string;        // max 200 chars
  description: string;         // max 4000 chars
  references: string[];
  competitor_node_id: string;  // Parent competitor
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

### CompetitorWeakness
```typescript
interface CompetitorWeakness {
  node_id: string;
  account_id: string;
  display_name: string;        // max 200 chars
  description: string;         // max 4000 chars
  references: string[];
  competitor_node_id: string;  // Parent competitor
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

### SubstituteProduct
```typescript
interface SubstituteProduct {
  node_id: string;
  account_id: string;
  product_name: string;          // max 200 chars
  description: string;           // max 4000 chars
  references: string[];
  product_detail_page?: string;  // Optional URL
  competitor_node_id: string;    // Parent competitor
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}
```

**Note:** `Risk`, `Opportunity`, and `ValueProposition` types already exist in the codebase (shared with business strategy)

---

## Existing Frontend Patterns

### File Structure (following existing patterns)

```
frontend/src/
├── pages/
│   ├── KnowledgeAccount.tsx         ✅ Exists - reference for structure
│   ├── Products.tsx                 ✅ Exists - reference for structure
│   └── KnowledgeCompetitors.tsx     ❌ TO BUILD
├── components/
│   ├── products/
│   │   └── ProductCategoriesManagement.tsx  ✅ Exists - reference for complex UI
│   └── competitors/                 ❌ TO BUILD
│       ├── CompetitorsManagement.tsx
│       └── CompetitorFlowNodes.tsx (if using React Flow)
├── services/
│   ├── productService.ts            ✅ Exists - reference pattern
│   ├── valuePropositionService.ts   ✅ Exists - shared
│   ├── riskService.ts              ✅ Exists - shared
│   ├── opportunityService.ts       ✅ Exists - shared
│   └── competitorService.ts        ❌ TO BUILD
│   └── competitorTacticService.ts  ❌ TO BUILD
│   └── competitorStrengthService.ts ❌ TO BUILD
│   └── competitorWeaknessService.ts ❌ TO BUILD
│   └── substituteProductService.ts ❌ TO BUILD
└── queries/
    ├── products.ts                  ✅ Exists - reference pattern
    └── competitors.ts               ❌ TO BUILD
```

### Component Patterns from KnowledgeAccount.tsx

1. **Layout**: Uses `<Layout pageTitle="..." maxWidth={false}>`
2. **Back Button**: "Back to Knowledge Base" button with `<ArrowLeft>` icon
3. **Card Structure**: `<Card>` with `<CardHeader>` and `<CardContent>`
4. **Edit Pattern**: Side sheet (`<Sheet>`) for editing content
5. **Dialogs**: Uses `<Dialog>` for create/edit, `<AlertDialog>` for delete confirmations
6. **Permissions**: `hasEditAccess` computed from auth context
7. **Tooltips**: Info icons with tooltips to explain sections

### Component Patterns from ProductCategoriesManagement.tsx

1. **Horizontal Scroll**: Categories displayed in scrollable row with chevron buttons
2. **React Flow Diagram**: Used to show hierarchical relationships (category → products)
3. **Node Selection**: Click node to open side sheet with details
4. **Context Menu**: Side sheet with view/edit/delete actions
5. **Value Propositions**: Nested section within side sheet
6. **Mutations**: React Query mutations for all CRUD operations
7. **Loading States**: Spinners and loading text
8. **Empty States**: Helpful messages when no data exists

### Service Pattern (from productService.ts)

```typescript
import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

interface ItemCreate { /* fields */ }
interface ItemUpdate { /* fields */ }
interface Item { /* all fields including node_id */ }
interface ItemListResponse {
  items: Item[];
  total_count: number;
}

class ItemService {
  async list(accountId: AccountId, skip = 0, limit = 1000): Promise<ItemListResponse> {
    const response = await api.get(`/api/v1/knowledge-graph/${accountId}/items`, {
      params: { skip, limit }
    });
    return response.data;
  }

  async create(accountId: AccountId, data: ItemCreate): Promise<Item> {
    const response = await api.post(`/api/v1/knowledge-graph/${accountId}/items`, data);
    return response.data;
  }

  async update(accountId: AccountId, nodeId: string, data: ItemUpdate): Promise<Item> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/items/${nodeId}`,
      data
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(`/api/v1/knowledge-graph/${accountId}/items/${nodeId}`);
  }
}

export const itemService = new ItemService();
```

### React Query Pattern (from queries/products.ts)

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { itemService } from "@/services/itemService";

export function useItems(accountId: string | null, skip = 0, limit = 1000) {
  return useQuery({
    queryKey: ["items", accountId, skip, limit],
    queryFn: () => itemService.list(accountId!, skip, limit),
    enabled: !!accountId,
  });
}

export function useCreateItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, item }: { accountId: string; item: ItemCreate }) =>
      itemService.create(accountId, item),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useUpdateItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: ItemUpdate;
    }) => itemService.update(accountId, nodeId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useDeleteItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, nodeId }: { accountId: string; nodeId: string }) =>
      itemService.delete(accountId, nodeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}
```

---

## UI/UX Design Considerations

### Page Structure Options

#### Option 1: Single Page with Tabs/Accordion
Similar to SWOT management in KnowledgeAccount.tsx:
- Competitive Environment description at top (editable card)
- Horizontal scrollable list of competitors
- Click competitor to expand details below
- Nested sections for tactics, strengths, weaknesses, substitute products

#### Option 2: Two-Level Navigation
Similar to Products page:
- Top level: List of competitors (horizontal scroll or grid)
- Click competitor opens detail view
- React Flow diagram showing competitor relationships:
  - Center: Competitor node
  - Below: Substitute products
  - Sides: Tactics, Strengths, Weaknesses
  - Clicking any node opens side sheet with details

#### Option 3: Combined Approach (Recommended)
- **Top Section**: Competitive Environment description (editable card)
- **Middle Section**: Horizontal scrollable competitor cards
- **Bottom Section**: When competitor selected, show React Flow diagram
- **Side Sheet**: Click any node to view/edit details

### Visual Elements

**Icons (from lucide-react):**
- Competitive Environment: `Globe` or `Target`
- Competitor: `Users` or `Building2`
- CompetitorTactic: `Megaphone` or `TrendingUp`
- CompetitorStrength: `ThumbsUp` or `Award`
- CompetitorWeakness: `ThumbsDown` or `AlertTriangle`
- SubstituteProduct: `Package` or `Box`
- Risk: `AlertTriangle` (already used in SWOT)
- Opportunity: `TrendingUp` (already used in SWOT)

**Color Scheme (following existing patterns):**
- Primary actions: `brand-light-blue` and `brand-medium-blue`
- Competitor cards: Similar to product category styling
- Strengths: Light green background
- Weaknesses: Light yellow/orange background
- Risks: Light red background (from SWOT)
- Opportunities: Light green background (from SWOT)

---

## Implementation Checklist

### Phase 1: Backend Services & Types
- [ ] Create `competitorService.ts`
- [ ] Create `competitorTacticService.ts`
- [ ] Create `competitorStrengthService.ts`
- [ ] Create `competitorWeaknessService.ts`
- [ ] Create `substituteProductService.ts`
- [ ] Create `competitiveEnvironmentService.ts`
- [ ] Define TypeScript interfaces for all models

### Phase 2: React Query Hooks
- [ ] Create `queries/competitors.ts` with all hooks:
  - `useCompetitiveEnvironment()`
  - `useUpdateCompetitiveEnvironment()`
  - `useCompetitors()`
  - `useCreateCompetitor()`
  - `useUpdateCompetitor()`
  - `useDeleteCompetitor()`
  - Similar hooks for tactics, strengths, weaknesses, substitute products
  - Reuse existing hooks for risks, opportunities, value propositions

### Phase 3: UI Components
- [ ] Create `components/competitors/CompetitorsManagement.tsx`
- [ ] Create `components/competitors/CompetitorFlowNodes.tsx` (if using React Flow)
- [ ] Create dialogs/sheets for CRUD operations
- [ ] Implement permissions checking (`hasEditAccess`)

### Phase 4: Main Page
- [ ] Create `pages/KnowledgeCompetitors.tsx`
- [ ] Integrate all components
- [ ] Add routing in app router
- [ ] Test all CRUD operations
- [ ] Test permissions

### Phase 5: Polish
- [ ] Add loading states
- [ ] Add empty states with helpful messages
- [ ] Add error handling and toast notifications
- [ ] Add tooltips for all sections
- [ ] Ensure responsive design
- [ ] Test with real data

---

## Key Differences from Products Page

1. **More Complex Hierarchy**: Competitors have 6 child node types vs. products having 2-3
2. **SWOT Integration**: Competitor strengths/weaknesses create risks/opportunities
3. **Shared Nodes**: Value propositions can belong to competitors OR substitute products
4. **Hub Node**: CompetitiveEnvironment is auto-created (can't be deleted)
5. **References**: All nodes support reference URLs (important for competitive intel)

---

## Testing Considerations

1. **Empty State**: No competitive environment yet (first-time user)
2. **Single Competitor**: Test with minimal data
3. **Multiple Competitors**: Test horizontal scroll behavior
4. **Deep Hierarchy**: Competitor with all child node types populated
5. **Permissions**: Test as viewer (read-only) and editor
6. **Deletion**: Test cascading delete rules (competitor with children)
7. **Shared Nodes**: Ensure value propositions, risks, opportunities display correctly

---

## Questions to Clarify

1. **Layout Preference**: Which of the 3 page structure options is preferred?
2. **Diagram Complexity**: Should we use React Flow for visualization, or simpler card-based layout?
3. **Filtering**: Do we need ability to filter/search competitors?
4. **Comparison View**: Should users be able to compare multiple competitors side-by-side?
5. **Risk/Opportunity Management**: Should these be editable inline, or link back to SWOT page?

---

## Notes for Multi-Session Implementation

- This file serves as comprehensive documentation for building competitive strategy frontend
- All backend endpoints are already implemented and tested
- Frontend patterns are well-established (follow KnowledgeAccount.tsx and ProductCategoriesManagement.tsx)
- Can be built incrementally: services first, then queries, then components, then main page
- TypeScript interfaces should be branded types where appropriate (e.g., `AccountId`, `NodeId`)
