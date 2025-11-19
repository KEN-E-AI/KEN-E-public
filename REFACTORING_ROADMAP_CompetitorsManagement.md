# Refactoring Roadmap: CompetitorsManagement.tsx

**Current State:** 3,155 lines (too large for maintainability)
**Target State:** ~300 lines main orchestrator + focused sub-components
**Estimated Effort:** 16-20 hours
**Priority:** MEDIUM (improves maintainability, not blocking functionality)

## Overview

The CompetitorsManagement component manages competitive analysis with 6 entity types (Competitor, Strength, Weakness, Tactic, Substitute Product, and cross-references to SWOT entities). This roadmap breaks down the refactoring into manageable phases.

## Current Component Structure

```
CompetitorsManagement.tsx (3,155 lines)
├── Lines 1-180: Imports + Hooks + State (180 lines)
├── Lines 180-530: Competitor CRUD handlers (350 lines)
├── Lines 530-880: Strength/Weakness handlers (350 lines)
├── Lines 880-1200: Substitute Product handlers (320 lines)
├── Lines 1200-1550: Tactic handlers (350 lines)
├── Lines 1550-1960: Cross-entity handlers (Risk/Opp/VP) (410 lines)
├── Lines 1960-2130: Main JSX + Competitor List (170 lines)
├── Lines 2130-2230: Competitor Modal + Delete Dialog (100 lines)
├── Lines 2230-2470: Child Creation Modal (multi-purpose) (240 lines)
├── Lines 2470-2570: Tactic Modal + Delete Dialog (100 lines)
├── Lines 2570-2900: Substitute Product linking UI (330 lines)
└── Lines 2900-3155: Graph visualization + misc (255 lines)
```

## Phase 1: Extract Modals (Priority 1) - 8-10 hours

### Why Start Here?
- Modals are self-contained UI components
- Easiest to extract with minimal coupling
- Immediate reduction of ~1,500 lines
- Low risk of breaking existing functionality

### 1.1 Create Directory Structure

```bash
mkdir -p frontend/src/components/competitors/modals
```

### 1.2 Extract CompetitorModal (Est: 1 hour)

**File:** `frontend/src/components/competitors/modals/CompetitorModal.tsx`

**Source Lines:** 2130-2202 (create modal), 2204-2230 (delete dialog)

**Props Interface:**
```typescript
interface CompetitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorCreate) => Promise<void>;
  initialData?: Competitor; // For edit mode
  mode: 'create' | 'edit';
}
```

**Key Features:**
- Display name input (max 200 chars)
- Description textarea (max 4000 chars)
- References array management
- Form validation
- Loading state during submission

**Pattern to Follow:**
```typescript
export const CompetitorModal = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  mode
}: CompetitorModalProps) => {
  const [formData, setFormData] = useState<CompetitorCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    references: initialData?.references || [],
  });

  const handleSubmit = async () => {
    await onSubmit(formData);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      {/* Modal content */}
    </Dialog>
  );
};
```

**Delete Dialog Pattern:**
```typescript
interface DeleteCompetitorDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  competitorName: string;
}
```

### 1.3 Extract StrengthModal (Est: 1 hour)

**File:** `frontend/src/components/competitors/modals/StrengthModal.tsx`

**Source Lines:** Part of 2230-2470 (child creation modal, strength section)

**Props Interface:**
```typescript
interface StrengthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorStrengthCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorStrength; // For edit mode
  mode: 'create' | 'edit';
}
```

**Key Features:**
- Display name input
- Description textarea
- References management
- Parent competitor context display
- Opportunity linking (future enhancement)

### 1.4 Extract WeaknessModal (Est: 1 hour)

**File:** `frontend/src/components/competitors/modals/WeaknessModal.tsx`

**Source Lines:** Part of 2230-2470 (child creation modal, weakness section)

**Props Interface:**
```typescript
interface WeaknessModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorWeaknessCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorWeakness;
  mode: 'create' | 'edit';
}
```

**Key Features:**
- Similar to StrengthModal
- Risk linking (future enhancement)

### 1.5 Extract TacticModal (Est: 1 hour)

**File:** `frontend/src/components/competitors/modals/TacticModal.tsx`

**Source Lines:** 2465-2570

**Props Interface:**
```typescript
interface TacticModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorTacticCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorTactic;
  mode: 'create' | 'edit';
}
```

### 1.6 Extract SubstituteProductModal (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/modals/SubstituteProductModal.tsx`

**Source Lines:** Part of 2230-2470 + 2570-2900 (product linking UI)

**Props Interface:**
```typescript
interface SubstituteProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: SubstituteProductCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: SubstituteProduct;
  mode: 'create' | 'edit';
  // Product linking
  onLinkProduct?: (substituteId: string, productId: string) => Promise<void>;
  onUnlinkProduct?: (substituteId: string, productId: string) => Promise<void>;
  linkedProducts?: Product[];
}
```

**Key Features:**
- Product name + description
- Product detail page URL
- References management
- Product linking interface (dropdown + link/unlink buttons)
- Show currently linked products

### 1.7 Extract Cross-Entity Modals (Est: 2.5 hours)

**RiskModal, OpportunityModal, ValuePropositionModal**

These modals connect competitive entities to SWOT/Product entities. Extract following same pattern as above.

**Files:**
- `frontend/src/components/competitors/modals/RiskModal.tsx`
- `frontend/src/components/competitors/modals/OpportunityModal.tsx`
- `frontend/src/components/competitors/modals/ValuePropositionModal.tsx`

### 1.8 Create Modal Index Export (Est: 15 min)

**File:** `frontend/src/components/competitors/modals/index.ts`

```typescript
export { CompetitorModal } from './CompetitorModal';
export { StrengthModal } from './StrengthModal';
export { WeaknessModal } from './WeaknessModal';
export { TacticModal } from './TacticModal';
export { SubstituteProductModal } from './SubstituteProductModal';
export { RiskModal } from './RiskModal';
export { OpportunityModal } from './OpportunityModal';
export { ValuePropositionModal } from './ValuePropositionModal';

export type { CompetitorModalProps } from './CompetitorModal';
// ... export all prop types
```

### 1.9 Update Main Component (Est: 1 hour)

Update CompetitorsManagement.tsx to use extracted modals:

```typescript
import {
  CompetitorModal,
  StrengthModal,
  WeaknessModal,
  // ... other modals
} from './modals';

// Replace inline modal JSX with:
<CompetitorModal
  isOpen={isCreateCompetitorModalOpen}
  onClose={() => setIsCreateCompetitorModalOpen(false)}
  onSubmit={handleCreateCompetitor}
  mode="create"
/>
```

**Expected Line Reduction:** ~1,500 lines removed → Down to ~1,655 lines

## Phase 2: Extract View Components (Priority 2) - 4-5 hours

### Why Second?
- Views depend on modals being extracted first
- Focused responsibility per view
- Further reduction of ~900 lines

### 2.1 Extract CompetitorsList (Est: 1 hour)

**File:** `frontend/src/components/competitors/CompetitorsList.tsx`

**Source Lines:** 1964-2004

**Props Interface:**
```typescript
interface CompetitorsListProps {
  competitors: Competitor[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
  isLoading: boolean;
  hasEditAccess: boolean;
}
```

**Features:**
- Horizontal scroll list
- Empty state handling
- Add button (conditional on hasEditAccess)
- Loading skeleton

### 2.2 Extract StrengthsView (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/views/StrengthsView.tsx`

**Props Interface:**
```typescript
interface StrengthsViewProps {
  competitorId: string;
  competitorName: string;
  strengths: CompetitorStrength[];
  opportunities: Opportunity[]; // Linked opportunities
  onAddStrength: () => void;
  onEditStrength: (strength: CompetitorStrength) => void;
  onDeleteStrength: (strengthId: string) => void;
  onAddOpportunity: (strengthId: string) => void;
  isLoading: boolean;
  hasEditAccess: boolean;
}
```

**Features:**
- Grid/list of strengths
- Nested opportunities display
- Add/Edit/Delete actions per strength
- Empty state

### 2.3 Extract WeaknessesView (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/views/WeaknessesView.tsx`

Similar to StrengthsView but for weaknesses + risks.

### 2.4 Extract SubstituteProductsView (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/views/SubstituteProductsView.tsx`

**Props Interface:**
```typescript
interface SubstituteProductsViewProps {
  competitorId: string;
  substituteProducts: SubstituteProduct[];
  linkedProducts: Map<string, Product[]>; // substituteId -> products
  valuePropositions: Map<string, ValueProposition[]>; // substituteId -> VPs
  onAddSubstitute: () => void;
  onEditSubstitute: (substitute: SubstituteProduct) => void;
  onDeleteSubstitute: (substituteId: string) => void;
  onLinkProduct: (substituteId: string) => void;
  onUnlinkProduct: (substituteId: string, productId: string) => void;
  onAddValueProposition: (substituteId: string) => void;
  isLoading: boolean;
  hasEditAccess: boolean;
}
```

**Expected Line Reduction:** ~900 lines removed → Down to ~755 lines

## Phase 3: Extract Custom Hooks (Priority 3) - 3-4 hours

### Why Last?
- Hooks depend on understanding full component logic
- Consolidates state management
- Final reduction to target ~300 lines

### 3.1 Extract useCompetitorSelection (Est: 1 hour)

**File:** `frontend/src/components/competitors/hooks/useCompetitorSelection.ts`

**Functionality:**
- Manage selected competitor state
- Sync with URL params (`?competitor=<id>`)
- Handle navigation
- Return `{ selectedId, selectedCompetitor, setSelected, clearSelection }`

**Source Logic:** Lines 186-191 + URL sync logic around line 175

### 3.2 Extract useCompetitorModals (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/hooks/useCompetitorModals.ts`

**Functionality:**
- Centralize all modal open/close state
- Return object with `openCompetitorModal`, `closeAllModals`, etc.
- Manage form data state for each modal type

**Benefits:**
- Single source of truth for modal state
- Easier to test
- Reduces main component clutter

### 3.3 Extract useCompetitorGraph (Est: 1.5 hours)

**File:** `frontend/src/components/competitors/hooks/useCompetitorGraph.ts`

**Functionality:**
- Generate ReactFlow nodes from competitor data
- Generate edges based on relationships
- Handle node click events
- Layout calculations

**Return Type:**
```typescript
interface UseCompetitorGraphReturn {
  nodes: Node[];
  edges: Edge[];
  onNodeClick: (event: React.MouseEvent, node: Node) => void;
}
```

**Expected Line Reduction:** ~350 lines removed → Down to ~400 lines

## Phase 4: Final Cleanup (Priority 4) - 1-2 hours

### 4.1 Simplify Main Component Structure

The final CompetitorsManagement.tsx should look like:

```typescript
export const CompetitorsManagement = ({ hasEditAccess }: Props) => {
  // Hooks
  const { selectedId, selectedCompetitor, setSelected } = useCompetitorSelection();
  const modals = useCompetitorModals();
  const graph = useCompetitorGraph(selectedCompetitor, mode);

  // Data fetching (React Query)
  const { data: competitorsData } = useCompetitors(...);
  const { data: strengthsData } = useCompetitorStrengths(...);
  // ... other queries

  // Mode state
  const [mode, setMode] = useState<CompetitorMode>("strengths");

  return (
    <>
      <CompetitorsList
        competitors={competitors}
        selectedId={selectedId}
        onSelect={setSelected}
        onAdd={modals.openCompetitorModal}
        hasEditAccess={hasEditAccess}
      />

      {selectedCompetitor && (
        <>
          <ModeSelector
            modes={COMPETITOR_MODES}
            value={mode}
            onChange={setMode}
          />

          {mode === "strengths" && (
            <StrengthsView
              competitorId={selectedId!}
              strengths={strengths}
              onAddStrength={modals.openStrengthModal}
              hasEditAccess={hasEditAccess}
            />
          )}

          {/* Other mode views */}

          <GraphVisualization
            nodes={graph.nodes}
            edges={graph.edges}
            onNodeClick={graph.onNodeClick}
          />
        </>
      )}

      {/* All modals */}
      <CompetitorModal {...modals.competitorModal} />
      <StrengthModal {...modals.strengthModal} />
      {/* ... other modals */}
    </>
  );
};
```

**Expected Final Size:** ~300-350 lines

### 4.2 Update Tests

Update CompetitorsManagement.test.tsx to account for new structure:
- Mock extracted components
- Test modal prop passing
- Test view switching logic

### 4.3 Documentation

Update component documentation:
- Add JSDoc comments to exported components
- Document props with TSDoc
- Add usage examples

## Testing Strategy

### After Each Phase

1. **Run existing tests:**
   ```bash
   npm test src/components/competitors/CompetitorsManagement.test.tsx
   ```

2. **Manual testing checklist:**
   - [ ] Can create competitor
   - [ ] Can select competitor
   - [ ] Can switch modes
   - [ ] Can add strength/weakness/substitute
   - [ ] Can link products to substitutes
   - [ ] Can delete entities
   - [ ] Graph visualization works
   - [ ] URL sync works

3. **Smoke test in browser:**
   - Load competitors page
   - Perform basic CRUD operations
   - Check console for errors

### New Tests to Add

After refactoring, add unit tests for extracted components:

```bash
frontend/src/components/competitors/
├── modals/
│   ├── CompetitorModal.test.tsx
│   ├── StrengthModal.test.tsx
│   └── ...
├── views/
│   ├── StrengthsView.test.tsx
│   └── ...
└── hooks/
    ├── useCompetitorSelection.test.ts
    └── ...
```

## Risk Mitigation

### High-Risk Areas

1. **State Management Coupling**
   - **Risk:** Modals/views tightly coupled to parent state
   - **Mitigation:** Use callback props, avoid direct state mutation

2. **React Query Cache Invalidation**
   - **Risk:** Breaking optimistic updates or cache invalidation
   - **Mitigation:** Keep mutation logic in main component initially

3. **Navigation/URL Sync**
   - **Risk:** Breaking browser back/forward
   - **Mitigation:** Test URL sync thoroughly after Phase 3

### Rollback Strategy

- Work on feature branch: `refactor/competitors-management-modals`
- Commit after each modal extraction
- If issues arise, can cherry-pick successful extractions
- Keep original component until all phases complete

## Success Metrics

- [ ] Main component reduced to <400 lines
- [ ] All existing tests pass
- [ ] No new console errors/warnings
- [ ] Manual QA passes all scenarios
- [ ] Code review approval
- [ ] TypeScript strict mode passes

## Timeline Estimate

| Phase | Task | Hours | Dependencies |
|-------|------|-------|--------------|
| 1.1   | Create directory | 0.1 | None |
| 1.2   | CompetitorModal | 1.0 | 1.1 |
| 1.3   | StrengthModal | 1.0 | 1.1 |
| 1.4   | WeaknessModal | 1.0 | 1.1 |
| 1.5   | TacticModal | 1.0 | 1.1 |
| 1.6   | SubstituteProductModal | 1.5 | 1.1 |
| 1.7   | Cross-entity modals | 2.5 | 1.1 |
| 1.8   | Modal index | 0.25 | 1.2-1.7 |
| 1.9   | Update main component | 1.0 | 1.8 |
| **Phase 1 Total** | | **9.35 hours** | |
| 2.1   | CompetitorsList | 1.0 | Phase 1 |
| 2.2   | StrengthsView | 1.5 | Phase 1 |
| 2.3   | WeaknessesView | 1.5 | Phase 1 |
| 2.4   | SubstituteProductsView | 1.5 | Phase 1 |
| **Phase 2 Total** | | **5.5 hours** | |
| 3.1   | useCompetitorSelection | 1.0 | Phase 2 |
| 3.2   | useCompetitorModals | 1.5 | Phase 2 |
| 3.3   | useCompetitorGraph | 1.5 | Phase 2 |
| **Phase 3 Total** | | **4.0 hours** | |
| 4.1   | Final cleanup | 0.5 | Phase 3 |
| 4.2   | Update tests | 1.0 | Phase 3 |
| 4.3   | Documentation | 0.5 | Phase 3 |
| **Phase 4 Total** | | **2.0 hours** | |
| **Grand Total** | | **20.85 hours** | |

## References

- CLAUDE.md Best Practices (especially C-9, O-1, O-2)
- Existing pattern: [ProductCategoriesManagement.tsx](frontend/src/components/products/ProductCategoriesManagement.tsx)
- Knowledge Graph Library: [components/knowledge-graph](frontend/src/components/knowledge-graph)

## Next Steps

1. **Get approval** for this refactoring approach
2. **Create Jira ticket** or GitHub issue
3. **Create feature branch:** `refactor/competitors-management`
4. **Start with Phase 1.2** (CompetitorModal) as proof of concept
5. **Review & iterate** before proceeding to remaining phases

---

*Document created: 2025-01-19*
*Last updated: 2025-01-19*
*Status: Ready for Implementation*
