# Design Change Propagation Workflow

This document describes how to handle design changes that occur during development and ensure all impacted artifacts are updated.

## Design Change Categories

| Category | Scope | Examples | Impact Level |
|----------|-------|----------|--------------|
| **Implementation Detail** | Current story only | Algorithm choice, library selection | Low |
| **Story Scope Change** | Current story + siblings | Adding/removing acceptance criteria | Medium |
| **Feature Scope Change** | Feature + downstream features | New API endpoint, data model change | High |
| **Architectural Change** | Multiple releases | Technology change, pattern change | Critical |

## When to Trigger Design Change Propagation

Trigger this workflow when ANY of these occur during development:

1. **Data Model Changes**
   - Adding/removing fields from schemas
   - Changing field types or constraints
   - Modifying relationships between entities

2. **API Changes**
   - Adding/removing endpoints
   - Changing request/response formats
   - Modifying authentication requirements

3. **Behavioral Changes**
   - Changing how a component processes data
   - Modifying error handling strategies
   - Altering the flow between components

4. **Technology Changes**
   - Switching libraries or frameworks
   - Changing infrastructure components
   - Modifying deployment strategies

5. **Constraint Changes**
   - Performance requirements changing
   - Security requirements changing
   - Compatibility requirements changing

---

## Design Decisions Database

A new Notion database to track design decisions and their impact.

### Schema

| Property | Type | Description |
|----------|------|-------------|
| Title | title | Brief description of the decision |
| Decision Date | date | When the decision was made |
| Context | rich_text | Why this decision was needed |
| Decision | rich_text | What was decided |
| Alternatives Considered | rich_text | Other options that were rejected |
| Consequences | rich_text | Impact on the system |
| Status | select | `Proposed`, `Accepted`, `Superseded`, `Deprecated` |
| Impact Level | select | `Low`, `Medium`, `High`, `Critical` |
| Triggering Story | relation | User Story where this decision was made |
| Affected Stories | relation | User Stories impacted by this decision |
| Affected Features | relation | Features impacted by this decision |
| Product | relation | KEN-E or MER-E |

### Database IDs
```
Design Decisions Database: 0b49b51c9ea04b1e9e828531512844fb
Design Decisions Data Source: a88ce7c8-1ebb-4634-a422-2c1abcd2daf9
```

**Note:** Relation properties need to be added manually in Notion:
- Triggering Story → User Stories
- Affected Stories → User Stories
- Affected Features → Features
- Product → Products

---

## Feature Dependencies Reference

Based on the MER-E design document dependency graph (§16.7), here are the feature dependencies:

### Phase 1 → Phase 2 Dependencies
| Feature | Depends On | Dependency Type |
|---------|-----------|-----------------|
| 2.1 Enhanced Eval UI | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 | Phase dependency |
| 2.2 Priority Queue | 2.1 | Direct |
| 2.3 Dashboard | 2.1 | Direct |
| 2.4 Staging Deploy | 1.6 | Direct |
| 2.5 Rollback | 2.4 | Direct |
| 2.6 Agent Detail | 2.1 | Direct |
| 2.7 Rec Review UI | 2.1 | Direct |

### Phase 2 → Phase 3 Dependencies
| Feature | Depends On | Dependency Type |
|---------|-----------|-----------------|
| 3.1 Alignment Analyzer | Phase 2 | Phase dependency |
| 3.2 Prompt Generator | 3.1 | Direct |
| 3.3 Rec Aggregator | 3.2 | Direct |
| 3.4 Pattern Detector | Phase 2 | Phase dependency |
| 3.5 Tool Usage Analyzer | 1.2, Phase 2 | Mixed |
| 3.6 Canary Deploy | 2.4 | Direct |
| 3.7 Monitoring | 3.6 | Direct |
| 3.8 Notifications | 3.3, 3.7 | Multiple |

### Phase 3 → Phase 4 Dependencies
| Feature | Depends On | Dependency Type |
|---------|-----------|-----------------|
| 4.1 Config Optimizer | Phase 3 | Phase dependency |
| 4.2 Experiment UI | 4.1 | Direct |
| 4.3 Factor Suggestions | 3.3 | Direct |
| 4.4 Anomaly Detection | 3.7 | Direct |
| 4.5 Feedback Requests | 3.3 | Direct |
| 4.6 Structural Detection | 3.5 | Direct |
| 4.7 Trend Analysis | 2.8 | Direct |

---

## Design Change Impact Analysis Process

When a design change is identified, follow this process:

### Step 1: Classify the Change

```
□ What changed?
  □ Data model (schema, fields, types)
  □ API (endpoints, contracts, formats)
  □ Behavior (processing, flow, logic)
  □ Technology (libraries, infrastructure)
  □ Constraints (performance, security)

□ What is the impact level?
  □ Low - Current story only
  □ Medium - Current feature's stories
  □ High - Downstream features affected
  □ Critical - Multiple releases affected
```

### Step 2: Identify Affected Artifacts

Based on impact level, identify what needs updating:

#### Low Impact (Implementation Detail)
- [ ] Current User Story acceptance criteria
- [ ] Current Session Log
- [ ] Code comments/documentation

#### Medium Impact (Story/Feature Scope)
- [ ] All items from Low Impact
- [ ] Sibling stories in the same Feature
- [ ] Feature acceptance criteria
- [ ] Design document (if applicable)

#### High Impact (Cross-Feature)
- [ ] All items from Medium Impact
- [ ] Downstream features (use dependency table above)
- [ ] Stories in downstream features
- [ ] Design document sections
- [ ] Release notes/checklist

#### Critical Impact (Architectural)
- [ ] All items from High Impact
- [ ] Multiple releases
- [ ] Product Vision (if fundamental change)
- [ ] All affected sprints
- [ ] Design document (major revision)

### Step 3: Create Design Decision Record

For Medium, High, or Critical changes, create a Design Decision:

```
notion-create-pages:
  parent:
    data_source_id: "[Design Decisions data_source_id]"
  pages:
    - properties:
        Title: "[Brief decision title]"
        date:Decision Date:start: "[YYYY-MM-DD]"
        date:Decision Date:is_datetime: 0
        Context: "[Why this decision was needed]"
        Decision: "[What was decided]"
        Alternatives Considered: "[Other options rejected]"
        Consequences: "[Impact on the system]"
        Status: "Accepted"
        Impact Level: "[Low/Medium/High/Critical]"
        Triggering Story: "[Story Page URL]"
        Product: "[Product Page URL]"
      content: |
        ## Decision Record

        ### Context
        [Detailed context about the situation]

        ### Decision
        [The decision that was made]

        ### Rationale
        [Why this decision was made over alternatives]

        ### Consequences
        [Both positive and negative impacts]

        ### Affected Components
        - [Component 1]
        - [Component 2]
```

### Step 4: Update Affected Stories

For each affected story:

1. **Add a comment** linking to the Design Decision:
   ```
   notion-create-comment:
     parent:
       page_id: "[Affected Story page ID]"
     rich_text:
       - type: "text"
         text:
           content: "⚠️ DESIGN CHANGE: This story is affected by [Decision Title]. See: [Decision URL]\n\nImpact: [How this story needs to change]"
   ```

2. **Update acceptance criteria** if they changed:
   ```
   notion-update-page:
     data:
       page_id: "[Story page ID]"
       command: "update_properties"
       properties:
         Acceptance Criteria: "[Updated criteria]"
   ```

3. **Re-estimate story points** if scope changed significantly

### Step 5: Update Affected Features

For each affected feature:

1. **Update Feature content** with the change:
   ```
   notion-update-page:
     data:
       page_id: "[Feature page ID]"
       command: "insert_content_after"
       selection_with_ellipsis: "## Acceptance Criteria..."
       new_str: "\n\n## Design Changes\n- [Date]: [Change description] - See [Decision URL]"
   ```

2. **Review and update** Feature acceptance criteria if needed

### Step 6: Update Design Document

For High or Critical changes, update `docs/MER-E_Design.md`:

1. **Identify affected sections** using the design-doc-mapping.md
2. **Make the necessary changes** to the design document
3. **Add a change note** at the relevant section
4. **Update the version/date** in the document header

### Step 7: Update Session Log

Document the design change in the current Session Log:

```
notion-update-page:
  data:
    page_id: "[Session Log page ID]"
    command: "update_properties"
    properties:
      Work Completed: "- [Work items]\n- ⚠️ DESIGN CHANGE: [Brief description]"
      Next Steps: "- [Next items]\n- Propagate design change to affected stories"
```

---

## Quick Reference: Common Design Change Scenarios

### Scenario 1: Data Model Field Addition

**Trigger:** Need to add a field to a Firestore/BigQuery schema

**Impact Analysis:**
1. Current story that discovered the need
2. Feature 1.5 (Database Schema Setup) if schema not yet deployed
3. Any features that read/write this data
4. UI components that display this data
5. API endpoints that expose this data

**Actions:**
1. Update design document §4.2 or §4.3
2. Update affected story acceptance criteria
3. Create Design Decision record
4. Add comments to downstream stories

### Scenario 2: API Endpoint Change

**Trigger:** Need to modify an API request/response format

**Impact Analysis:**
1. Current story implementing the endpoint
2. Feature 1.6 (Basic API Endpoints) for contract changes
3. Frontend features that call the API
4. Any integration tests

**Actions:**
1. Update design document §10.3
2. Update frontend stories that use this API
3. Create Design Decision record
4. Update API documentation

### Scenario 3: Technology/Library Change

**Trigger:** Need to switch to a different library or approach

**Impact Analysis:**
1. Current story that discovered the issue
2. All stories in the same Feature
3. Any features using the same technology
4. Configuration/setup stories

**Actions:**
1. Update design document relevant section
2. Update CLAUDE.md if it affects development workflow
3. Create Design Decision record
4. Re-estimate affected stories

---

## Dependency Update Protocol

When a story is completed or changed, check if downstream stories need updates:

### For the Current Story:
1. Look up the Feature number
2. Find dependent features in the dependency table
3. For each dependent feature, review its stories
4. Add comments to any stories that might be affected

### Dependency Check Questions:
- Does this story's output become another story's input?
- Does this story define an interface that other stories consume?
- Does this story establish a pattern that other stories follow?
- Does this story create infrastructure that other stories depend on?

If YES to any, document the dependency and ensure downstream stories are aware.
