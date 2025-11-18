# Competitive Strategy Frontend Implementation Progress

**Date Started:** 2025-01-18
**Current Status:** Services & Hooks Complete - Components In Progress

---

## ✅ COMPLETED

### Backend API Fixes (Issue #1)
- Fixed 21 list endpoints missing `response_model_class` parameter across:
  - business.py (4 endpoints)
  - competitive.py (5 endpoints)
  - marketing.py (6 endpoints)
  - brand.py (6 endpoints)
- Committed: `fix: add missing response_model_class parameter to all list_nodes calls`

### Frontend Services Created
All TypeScript service files created in `frontend/src/services/`:
- ✅ `competitiveEnvironmentService.ts` - Hub node GET/UPDATE operations
- ✅ `competitorService.ts` - Full CRUD for Competitor nodes
- ✅ `competitorTacticService.ts` - Full CRUD for Tactics
- ✅ `competitorStrengthService.ts` - Full CRUD for Strengths
- ✅ `competitorWeaknessService.ts` - Full CRUD for Weaknesses
- ✅ `substituteProductService.ts` - Full CRUD for Substitute Products

### Frontend React Query Hooks Created
- ✅ `frontend/src/queries/competitors.ts` - Complete with all hooks for:
  - Competitive Environment (get, update)
  - Competitors (list, get, create, update, delete)
  - Competitor Tactics (list, create, update, delete)
  - Competitor Strengths (list, create, update, delete)
  - Competitor Weaknesses (list, create, update, delete)
  - Substitute Products (list, create, update, delete)

---

## 🚧 IN PROGRESS / TODO

### Components to Create

#### 1. CompetitorFlowNodes Component
**File:** `frontend/src/components/competitors/CompetitorFlowNodes.tsx`

**Nodes Needed:**
- `CompetitorNode` - Center node with display_name
- `CompetitorStrengthNode` - For strengths mode
- `CompetitorWeaknessNode` - For weaknesses mode
- `SubstituteProductNode` - For substitute products mode
- `RiskNode` - Reuse from SWOT (risks from competitor strengths)
- `OpportunityNode` - Reuse from SWOT (opportunities from competitor weaknesses)
- `OurProductNode` - For showing our products that compete with substitutes

**Pattern:** Follow `frontend/src/components/swot/SwotFlowNodes.tsx`

#### 2. CompetitorsManagement Component
**File:** `frontend/src/components/competitors/CompetitorsManagement.tsx`

**Structure:**
```
- Mode Switcher (3-way toggle): Strengths / Weaknesses / Substitute Products
- Horizontal Scrollable Competitor List (like ProductCategories)
- React Flow Diagram Card (600px height)
  - Strengths mode: Competitor → CompetitorStrength → Risk
  - Weaknesses mode: Competitor → CompetitorWeakness → Opportunity
  - Substitute Products mode: Competitor → SubstituteProduct → Our Products
- Side Sheet for node details
  - Competitor: show tactics section
  - SubstituteProduct: show value propositions section
  - Others: standard display
```

**Pattern:** Combination of:
- `frontend/src/components/swot/SwotManagement.tsx` (mode switcher, React Flow)
- `frontend/src/components/products/ProductCategoriesManagement.tsx` (horizontal scroll)

#### 3. Update KnowledgeCompetitors Page
**File:** `frontend/src/pages/KnowledgeCompetitors.tsx`

**Add These Sections (in order):**
1. **Competitive Environment Card**
   - Display description from CompetitiveEnvironment node
   - Pencil icon for inline editing
   - Tooltip: "Define the competitive landscape and strategy for identifying key competitors. This includes factors like geography, market segment, brand positioning, and product substitutability."

2. **Competitor Keywords Card**
   - Wrap existing `<CompetitorsConfiguration />` in a Card
   - Add header: `<h3>Competitor Keywords</h3>`

3. **Competitors Management Card**
   - New `<CompetitorsManagement hasEditAccess={hasEditAccess} />`

### Testing Checklist

- [ ] Create competitor via UI
- [ ] Edit competitor details
- [ ] Delete competitor (with/without children)
- [ ] Add competitor strength
- [ ] Add competitor weakness
- [ ] Add substitute product
- [ ] Add tactics to competitor
- [ ] Add value propositions to substitute product
- [ ] Test risk creation from competitor strength
- [ ] Test opportunity creation from competitor weakness
- [ ] Test permissions (view-only user vs edit user)
- [ ] Test all 3 modes (Strengths / Weaknesses / Substitute Products)
- [ ] Test horizontal scrolling with many competitors
- [ ] Test React Flow diagram navigation
- [ ] Test side sheet open/close/edit
- [ ] Test unsaved changes warning

---

## Design Decisions Confirmed

### Icons (from lucide-react)
- Competitive Environment: `Target` or `Globe`
- Competitor: `Users` or `Building2`
- CompetitorTactic: `Megaphone` or `TrendingUp`
- CompetitorStrength: `ThumbsUp` or `Award`
- CompetitorWeakness: `ThumbsDown` or `AlertTriangle`
- SubstituteProduct: `Package` or `Box`
- Risk: `ShieldAlert` (from SWOT)
- Opportunity: `Star` (from SWOT)

### Color Scheme
- Competitor cards: Similar to product category styling (light blue)
- Strengths: Light green background (match SWOT)
- Weaknesses: Light yellow/orange background (match SWOT)
- Risks: Light red background (from SWOT)
- Opportunities: Light green background (from SWOT)

### API Endpoints
All endpoints use `/api/v1/knowledge-graph/{account_id}/` prefix:
- `GET /competitive-environment`
- `PATCH /competitive-environment`
- `GET /competitors` with pagination
- `POST /competitors`
- `PATCH /competitors/{node_id}`
- `DELETE /competitors/{node_id}`
- Similar CRUD for tactics, strengths, weaknesses, substitute-products

### Relationships to Display
1. **Strengths Mode**: `Competitor -[:HAS_STRENGTH]-> CompetitorStrength -[:CREATES]-> Risk`
2. **Weaknesses Mode**: `Competitor -[:HAS_WEAKNESS]-> CompetitorWeakness -[:CREATES]-> Opportunity`
3. **Substitute Products Mode**: `Competitor -[:OFFERS_PRODUCT]-> SubstituteProduct <-[:MAY_BE_SUBSTITUTED_FOR]- Product`

---

## Notes for Next Session

- The backend API is fully functional and tested
- All service layer code is complete
- Need to build the UI components following existing patterns
- CompetitorsManagement will be the largest component (~1500-2000 lines based on SwotManagement + ProductCategoriesManagement patterns)
- Should be able to complete components in 1-2 sessions
- Final testing and polish will be the last step

---

## Files Created This Session

### Services
1. `frontend/src/services/competitiveEnvironmentService.ts`
2. `frontend/src/services/competitorService.ts`
3. `frontend/src/services/competitorTacticService.ts`
4. `frontend/src/services/competitorStrengthService.ts`
5. `frontend/src/services/competitorWeaknessService.ts`
6. `frontend/src/services/substituteProductService.ts`

### Queries
7. `frontend/src/queries/competitors.ts`

### Documentation
8. `COMPETITIVE_STRATEGY_FRONTEND_NOTES.md` - Comprehensive implementation guide
9. `COMPETITIVE_FRONTEND_PROGRESS.md` - This file (session tracker)

### Backend Fixes
10. Modified `api/src/kene_api/routers/knowledge_graph/business.py`
11. Modified `api/src/kene_api/routers/knowledge_graph/competitive.py`
12. Modified `api/src/kene_api/routers/knowledge_graph/marketing.py`
13. Modified `api/src/kene_api/routers/knowledge_graph/brand.py`
