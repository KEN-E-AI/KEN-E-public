Of course. Here is the Markdown conversion of the attached file.

# Knowledge Graph Design: Marketing Strategy

## 1\. Executive Summary

This document provides the definitive specification for modeling and ingesting marketing and customer intelligence into the knowledge graph.

-----

## 2\. Updated Pydantic Model

UPDATE IN FILE: `app/adk/agents/strategy_agent/agents.py`

```python
from typing import List
from pydantic import BaseModel, Field, RootModel

class IdealCustomerProfile(BaseModel):
    """
    A detailed profile of an ideal customer for a specific product category.
    """
    display_name: str = Field(..., description="A short and unique name for the customer profile.")
    narrative: str = Field(
        ...,
        description="A narrative synthesizing the persona's name, background, pain points, core needs, buying motivations, and preferred communication channels."
    )
    problem_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description="A detailed strategy for making this persona aware of the problem the product solves, including key channels and touchpoints."
    )
    brand_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description="A detailed strategy for making this persona aware of the company's brand and products, demonstrating the value proposition."
    )
    consideration_strategy: str = Field(
        ...,
        max_length=4000,
        description="A strategy to persuade this persona to evaluate the company's offerings, detailing their evaluation process and key marketing touchpoints."
    )
    conversion_strategy: str = Field(
        ...,
        max_length=4000,
        description="A strategy to convert this persona into a paying customer, identifying critical factors and influential touchpoints in the purchasing decision."
    )
    loyalty_strategy: str = Field(
        ...,
        max_length=4000,
        description="A strategy to foster loyalty and advocacy from this persona post-purchase, outlining influential factors and touchpoints for retention."
    )

class ProductCategory(BaseModel):
    """
    Contains the research findings for a specific product category.
    """
    category_name: str = Field(
        ...,
        description="The name of the product or service category being analyzed."
    )
    ideal_customer_profiles: List[IdealCustomerProfile] = Field(
        ...,
        min_items=2,
        max_items=5,
        description="A list of 2 to 5 ideal customer profiles for this product category."
    )

# The new root model is a list of product category research results.
class ResearchReport(RootModel[List[ProductCategory]]):
    """
    The root model for the research report, containing a list of findings for each product category.
    """
    root: List[ProductCategory]
```

-----

## Marketing Strategy Nodes

**Important Implementation Notes:**

1. **Strategy Label**: All marketing strategy nodes receive TWO labels in Neo4j:
   - Specific node type label (e.g., `CustomerProfile`, `ProblemAwarenessStrategy`, `BrandAwarenessStrategy`)
   - Generic `Strategy` label for embedding search functionality

2. **Dual-Parent Architecture**: Marketing strategy nodes (ProblemAwareness, BrandAwareness, Consideration, Conversion, Loyalty) are scoped to BOTH ProductCategory AND CustomerProfile:
   - Each strategy node represents the marketing approach for a **specific (ProductCategory, CustomerProfile) pair**
   - node_id format: `{strategy_type}_{product_category_id}_{customer_profile_id}`
   - A CustomerProfile can have multiple instances of the same strategy type (one per ProductCategory)
   - Example: "Marketing Mary" has different ProblemAwarenessStrategies for "Cloud Services" vs "AI Tools"

3. **Bidirectional Relationships**:
   - `CustomerProfile -[:BELONGS_TO]-> Account` (profile links to account)
   - `ProductCategory -[:IS_MARKETED_TO]-> CustomerProfile` (category targets profile)
   - All strategy nodes have `BELONGS_TO` relationship to Account

4. **Dual Relationships for Strategy Nodes**:
   Each strategy node has TWO parent relationships:

   **From CustomerProfile**:
   - `CustomerProfile -[:DISCOVERS_THE_PROBLEM_BY]-> ProblemAwarenessStrategy`
   - `CustomerProfile -[:DISCOVERS_OUR_BRAND_BY]-> BrandAwarenessStrategy`
   - `CustomerProfile -[:CONSIDERS_OUR_BRAND_BECAUSE]-> ConsiderationStrategy`
   - `CustomerProfile -[:PURCHASES_OUR_BRAND_BECAUSE]-> ConversionStrategy`
   - `CustomerProfile -[:BECOMES_AN_ADVOCATE_BECAUSE]-> LoyaltyStrategy`

   **From ProductCategory** (enables scoping strategies to specific categories):
   - `ProductCategory -[:HAS_PROBLEM_AWARENESS_STRATEGY]-> ProblemAwarenessStrategy`
   - `ProductCategory -[:HAS_BRAND_AWARENESS_STRATEGY]-> BrandAwarenessStrategy`
   - `ProductCategory -[:HAS_CONSIDERATION_STRATEGY]-> ConsiderationStrategy`
   - `ProductCategory -[:HAS_CONVERSION_STRATEGY]-> ConversionStrategy`
   - `ProductCategory -[:HAS_LOYALTY_STRATEGY]-> LoyaltyStrategy`

5. **Parent ID Storage**: Strategy nodes store parent node_ids as properties for query performance:
   - `customer_profile_node_id`: Links to the CustomerProfile
   - `product_category_node_id`: Links to the ProductCategory
   - This enables efficient filtering and pagination without relationship traversal

6. **References Field**: All marketing nodes support a `references` field (array of strings) for source URLs or documentation links

7. **Cascade Deletion**: Deleting a CustomerProfile cascades:
   - Deletes ALL strategy nodes linked to that profile (across all ProductCategories)
   - Deletes ALL IS_MARKETED_TO relationships
   - Ensures no orphaned strategy nodes remain

8. **Unique Constraint**: CustomerProfile display_name must be unique within an account (case-insensitive)

-----

### CustomerProfile Node

A central hub for all information related to the ideal customer profile.

**Note**: CustomerProfile is created standalone. Strategy nodes are created separately when linking the profile to a ProductCategory.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the CustomerProfile. Generated by the system when the node is created. | `icp_c6051eee55b647ab81a80ffab37295e2` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `CustomerProfile` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short, unique name for the customer profile (persona name). Stored in lowercase for case-insensitive matching. | `marketing mary` |
| **narrative** | string | A narrative that synthesizes the persona's background, key pain points, core needs, primary buying motivations, and their preferred communication channels. | `Marketing Mary is a 35-year-old marketing director at a mid-sized SaaS company. She struggles with attribution tracking across multiple channels and needs tools that integrate with her existing martech stack. She prefers learning through webinars and case studies.` |
| **references** | list[string] | Array of source URLs or documentation links supporting this customer profile. | `["https://example.com/customer-research", "https://surveys.com/results"]` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **CustomerProfile** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **CustomerProfile** | \<-[:IS\_MARKETED\_TO]- | ProductCategory | Identifies an ideal customer profile that is targeted for a given product category. |
| **CustomerProfile** | -[:DISCOVERS\_THE\_PROBLEM\_BY]-\> | ProblemAwarenessStrategy | Identifies the strategy for making this customer profile aware of the problem that is solved by our product category. |
| **CustomerProfile** | -[:DISCOVERS\_OUR\_BRAND\_BY]-\> | BrandAwarenessStrategy | Identifies the strategy for making this customer profile aware of our brand and its value proposition. |
| **CustomerProfile**| -[:CONSIDERS\_OUR\_BRAND\_BECAUSE]-\>| ConsiderationStrategy | Identifies the strategy for persuading prospective customers within this profile who are currently evaluating products in this category to evaluate our brand. |
| **CustomerProfile**| -[:PURCHASES\_OUR\_BRAND\_BECAUSE]-\>| ConversionStrategy | Identifies the strategy for persuading prospective customers who are currently shopping to purchase our brand. |
| **CustomerProfile**| -[:BECOMES\_AN\_ADVOCATE\_BECAUSE]-\>| LoyaltyStrategy | Identifies the strategy for building loyalty with existing customers within this customer profile. |

-----

### ProblemAwarenessStrategy Node

**Purpose**: To store the company's high level strategy for making a specific ideal customer profile aware of the problems that are solved by a specific product or service category.

**Note**: This strategy is scoped to a specific (ProductCategory, CustomerProfile) pair. The same CustomerProfile may have different problem awareness strategies for different product categories.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the ProblemAwarenessStrategy. Format: `problemaware_{product_category_id}_{customer_profile_id}` | `problemaware_productcat_abc123_icp_xyz789` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `ProblemAwarenessStrategy` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description** | string | Describes the problem that the product category solves for this ideal customer profile, and creates a detailed strategy for helping prospective customers become aware of this problem | `Hungry Henry hates Mondays…` |
| **references** | list[string] | Array of source URLs or documentation links. | `["https://example.com/research"]` |
| **customer\_profile\_node\_id** | string | The CustomerProfile node_id this strategy applies to. Stored as property for query performance. | `icp_xyz789` |
| **product\_category\_node\_id** | string | The ProductCategory node_id this strategy applies to. Stored as property for query performance. | `productcat_abc123` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **ProblemAwarenessStrategy** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **ProblemAwarenessStrategy** | \<-[:DISCOVERS\_THE\_PROBLEM\_BY]- | CustomerProfile | Identifies the strategy for making this customer profile aware of the problem that is solved by our product category. |
| **ProblemAwarenessStrategy** | \<-[:HAS\_PROBLEM\_AWARENESS\_STRATEGY]- | ProductCategory | Links the strategy to the specific product category it applies to. |

-----

### BrandAwarenessStrategy Node

**Purpose**: To store the company's high level strategy for making a specific ideal customer profile aware of the brand and the products or services that they offer within a specific category.

**Note**: This strategy is scoped to a specific (ProductCategory, CustomerProfile) pair.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the BrandAwarenessStrategy. Format: `brandaware_{product_category_id}_{customer_profile_id}` | `brandaware_productcat_abc123_icp_xyz789` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `BrandAwarenessStrategy` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description** | string | Describes how the company might make the prospective customers within this ideal customer profile aware of the brand or its products or services within a specific category. | `Hungry Henry loves Facebook Marketplace` |
| **references** | list[string] | Array of source URLs or documentation links. | `["https://example.com/brand-research"]` |
| **customer\_profile\_node\_id** | string | The CustomerProfile node_id this strategy applies to. | `icp_xyz789` |
| **product\_category\_node\_id** | string | The ProductCategory node_id this strategy applies to. | `productcat_abc123` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **BrandAwarenessStrategy** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **BrandAwarenessStrategy** | \<-[:DISCOVERS\_OUR\_BRAND\_BY]- | CustomerProfile | Identifies the strategy for making this customer profile aware of our brand and its value proposition. |
| **BrandAwarenessStrategy** | \<-[:HAS\_BRAND\_AWARENESS\_STRATEGY]- | ProductCategory | Links the strategy to the specific product category it applies to. |

-----

### ConsiderationStrategy Node

**Purpose**: To store the company's high level strategy for encouraging a specific ideal customer profile to consider the products or services that they offer within a specific category.

**Note**: This strategy is scoped to a specific (ProductCategory, CustomerProfile) pair.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the ConsiderationStrategy. Format: `consideration_{product_category_id}_{customer_profile_id}` | `consideration_productcat_abc123_icp_xyz789` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `ConsiderationStrategy` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description**| string | Describes how prospective customers who meet the ideal customer profile evaluate products or services within this product category, what motivates them, and the marketing channels and touchpoints that help them decide. | `Hungry Henry uses Yelp to find local tacos…` |
| **references** | list[string] | Array of source URLs or documentation links. | `["https://example.com/consideration-research"]` |
| **customer\_profile\_node\_id** | string | The CustomerProfile node_id this strategy applies to. | `icp_xyz789` |
| **product\_category\_node\_id** | string | The ProductCategory node_id this strategy applies to. | `productcat_abc123` |
| **created\_time**| timestamp| The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified**| timestamp| The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by**| string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **ConsiderationStrategy** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **ConsiderationStrategy** | \<-[:CONSIDERS\_OUR\_BRAND\_BECAUSE]- | CustomerProfile | Identifies the strategy for persuading prospective customers within this profile who are currently evaluating products in this category to evaluate our brand. |
| **ConsiderationStrategy** | \<-[:HAS\_CONSIDERATION\_STRATEGY]- | ProductCategory | Links the strategy to the specific product category it applies to. |

-----

### ConversionStrategy Node

**Purpose**: To store the company's high level strategy for persuading the ideal customer profile to purchase their products or services within a specific product category.

**Note**: This strategy is scoped to a specific (ProductCategory, CustomerProfile) pair.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the ConversionStrategy. Format: `conversion_{product_category_id}_{customer_profile_id}` | `conversion_productcat_abc123_icp_xyz789` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `ConversionStrategy` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description**| string | Describes the specific action that a prospective customer takes to make a purchase, and then identifies the critical factors and influential touchpoints that lead prospects within this ideal customer profile to make a final purchasing decision. | `Hungry Henry purchases tacos through the DoorDash app…` |
| **references** | list[string] | Array of source URLs or documentation links. | `["https://example.com/conversion-research"]` |
| **customer\_profile\_node\_id** | string | The CustomerProfile node_id this strategy applies to. | `icp_xyz789` |
| **product\_category\_node\_id** | string | The ProductCategory node_id this strategy applies to. | `productcat_abc123` |
| **created\_time**| timestamp| The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified**| timestamp| The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by**| string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **ConversionStrategy** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **ConversionStrategy** | \<-[:PURCHASES\_OUR\_BRAND\_BECAUSE]- | CustomerProfile | Identifies the strategy for persuading prospective customers who are currently shopping to purchase our brand. |
| **ConversionStrategy** | \<-[:HAS\_CONVERSION\_STRATEGY]- | ProductCategory | Links the strategy to the specific product category it applies to. |

-----

### LoyaltyStrategy Node

**Purpose**: To store the company's high level strategy for persuading the ideal customer profile to become an advocate for their products or services within a specific product category after making a purchase.

**Note**: This strategy is scoped to a specific (ProductCategory, CustomerProfile) pair.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the LoyaltyStrategy. Format: `loyalty_{product_category_id}_{customer_profile_id}` | `loyalty_productcat_abc123_icp_xyz789` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `LoyaltyStrategy` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description**| string | Describes the post-purchase actions that loyal customers take after completing a purchase, and lists the influential factors and touchpoints that foster retention and advocacy. | `Hungry Henry tells his social media followers…` |
| **references** | list[string] | Array of source URLs or documentation links. | `["https://example.com/loyalty-research"]` |
| **customer\_profile\_node\_id** | string | The CustomerProfile node_id this strategy applies to. | `icp_xyz789` |
| **product\_category\_node\_id** | string | The ProductCategory node_id this strategy applies to. | `productcat_abc123` |
| **created\_time**| timestamp| The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified**| timestamp| The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by**| string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **LoyaltyStrategy** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **LoyaltyStrategy** | \<-[:BECOMES\_AN\_ADVOCATE\_BECAUSE]- | CustomerProfile | Identifies the strategy for building loyalty with existing customers within this customer profile. |
| **LoyaltyStrategy** | \<-[:HAS\_LOYALTY\_STRATEGY]- | ProductCategory | Links the strategy to the specific product category it applies to. |

-----

## Rollup Marketing Strategy Nodes

**Purpose**: Consolidate all individual marketing strategies into a single company-wide marketing strategy.

After all individual (ProductCategory × CustomerProfile) strategies are created, the system automatically generates:
1. One **RollupMarketingStrategy** hub node - central entry point for consolidated strategy
2. Five rollup strategy nodes - one per funnel stage, consolidating all individual strategies of that type

**Key Characteristics**:
- **Automatic creation**: Generated during account setup, after individual strategies complete
- **Editable**: Full CRUD operations via API endpoints
- **Bidirectional traceability**: Links to individual strategies via [:CAN\_BE\_CUSTOMIZED\_BY]
- **Same node types**: Rollup strategies use same labels as individuals (e.g., both are ProblemAwarenessStrategy:Strategy)
- **Distinguished by node\_id**: Rollup node\_ids start with "rollup\_", individuals don't

-----

### RollupMarketingStrategy Node (Hub)

**Purpose**: Central hub node that links the Account to all consolidated marketing strategies.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | Deterministic identifier for the rollup hub. | `rollup_marketing_hub_{account_id}` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | The node type in neo4j. | `RollupMarketingStrategy` |
| **label** | string | The strategy label for embedding search. | `Strategy` |
| **description** | string | Description of the consolidated marketing strategy. | `Consolidated marketing strategy for the entire business` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-12-10 10:00:00.000000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-12-10 10:00:00.000000 UTC |
| **created\_by** | string | User who created the node, or "System" if auto-generated. | `System` |
| **last\_modified\_by** | string | User who last modified the node. | `John Doe` |
| **embedding** | list | Vector embeddings for search. Initially null. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **RollupMarketingStrategy** | -[:BELONGS\_TO]-\> | Account | Standard relationship for all Strategy nodes. |
| **RollupMarketingStrategy** | -[:INCREASES\_CUSTOMERS\_BY]-\> | Account | Links the rollup hub to its account. |
| **RollupMarketingStrategy** | -[:INCREASES\_PROBLEM\_AWARENESS\_BY]-\> | ProblemAwarenessStrategy | Links hub to problem awareness rollup strategy. |
| **RollupMarketingStrategy** | -[:INCREASES\_BRAND\_AWARENESS\_BY]-\> | BrandAwarenessStrategy | Links hub to brand awareness rollup strategy. |
| **RollupMarketingStrategy** | -[:INCREASES\_CUSTOMERS\_CONSIDERING\_PURCHASE\_BY]-\> | ConsiderationStrategy | Links hub to consideration rollup strategy. |
| **RollupMarketingStrategy** | -[:INCREASES\_PAYING\_CUSTOMERS\_BY]-\> | ConversionStrategy | Links hub to conversion rollup strategy. |
| **RollupMarketingStrategy** | -[:INCREASES\_LOYAL\_CUSTOMERS\_BY]-\> | LoyaltyStrategy | Links hub to loyalty rollup strategy. |

-----

### Rollup Strategy Nodes (Problem Awareness, Brand Awareness, Consideration, Conversion, Loyalty)

**Purpose**: Consolidated strategy nodes that summarize all individual strategies for a specific funnel stage.

**Important**: Rollup strategies use the SAME node types as individual strategies:
- Both rollup and individual problem awareness strategies are `ProblemAwarenessStrategy:Strategy`
- Distinguished by node\_id pattern: rollup node\_ids start with `rollup_`, individual node\_ids don't

**Example: Rollup ProblemAwarenessStrategy**

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | Deterministic identifier. Format: `rollup_{stage}_{account_id}` | `rollup_problemaware_acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **account\_id** | string | The account identifier this node belongs to. | `acc_ab8cfbbb02b84d128f955fb98382c0b2` |
| **label** | string | Same node type as individual strategies. | `ProblemAwarenessStrategy` |
| **label** | string | Strategy label for embedding search. | `Strategy` |
| **description** | string | Consolidated summary of all problem awareness strategies. | `Summary combining strategies from all customer profiles and product categories...` |
| **references** | list[string] | Aggregated references from all individual strategies. | `["https://example.com/research1", "https://example.com/research2"]` |
| **created\_time** | timestamp | When the rollup was created. | 2025-12-10 10:00:00.000000 UTC |
| **last\_modified** | timestamp | When the rollup was last modified | 2025-12-10 10:00:00.000000 UTC |
| **created\_by** | string | User who created, or "System" if auto-generated. | `System` |
| **last\_modified\_by** | string | User who last modified the node. | `John Doe` |
| **embedding** | list | Vector embeddings for search. Initially null. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **ProblemAwarenessStrategy (rollup)** | -[:BELONGS\_TO]-\> | Account | Standard relationship for all Strategy nodes. |
| **ProblemAwarenessStrategy (rollup)** | \<-[:INCREASES\_PROBLEM\_AWARENESS\_BY]- | RollupMarketingStrategy | Links from the hub to this rollup strategy. |
| **ProblemAwarenessStrategy (rollup)** | -[:CAN\_BE\_CUSTOMIZED\_BY]-\> | ProblemAwarenessStrategy (individual) | Links rollup to each individual strategy it consolidates. Multiple relationships, one per individual strategy. |

**Note**: The same structure applies to the other 4 rollup strategy types:
- `RollupBrandAwarenessStrategy` (node\_id: `rollup_brandaware_{account_id}`)
- `RollupConsiderationStrategy` (node\_id: `rollup_consideration_{account_id}`)
- `RollupConversionStrategy` (node\_id: `rollup_conversion_{account_id}`)
- `RollupLoyaltyStrategy` (node\_id: `rollup_loyalty_{account_id}`)

-----

### Complete Rollup Graph Structure

```
Account
  ↑
  [:INCREASES_CUSTOMERS_BY]
  |
RollupMarketingStrategy (hub: rollup_marketing_hub_{account_id})
  |
  ├─[:INCREASES_PROBLEM_AWARENESS_BY]──────→ ProblemAwarenessStrategy (rollup)
  |                                             ├─[:CAN_BE_CUSTOMIZED_BY]→ ProblemAwarenessStrategy (category1×profile1)
  |                                             ├─[:CAN_BE_CUSTOMIZED_BY]→ ProblemAwarenessStrategy (category1×profile2)
  |                                             ├─[:CAN_BE_CUSTOMIZED_BY]→ ProblemAwarenessStrategy (category2×profile1)
  |                                             └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all problem awareness strategies)
  |
  ├─[:INCREASES_BRAND_AWARENESS_BY]────────→ BrandAwarenessStrategy (rollup)
  |                                             └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all brand awareness strategies)
  |
  ├─[:INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY]→ ConsiderationStrategy (rollup)
  |                                                    └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all consideration strategies)
  |
  ├─[:INCREASES_PAYING_CUSTOMERS_BY]───────→ ConversionStrategy (rollup)
  |                                             └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all conversion strategies)
  |
  └─[:INCREASES_LOYAL_CUSTOMERS_BY]────────→ LoyaltyStrategy (rollup)
                                                └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all loyalty strategies)
```

-----

### Querying Rollup Strategies

**Get the rollup hub with all linked rollup strategies:**
```cypher
MATCH (hub:RollupMarketingStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
OPTIONAL MATCH (hub)-[r]->(rollup:Strategy)
WHERE type(r) STARTS WITH 'INCREASES_'
RETURN hub, collect({type: type(r), strategy: rollup}) as linked_strategies
```

**Get a rollup strategy with all individual strategies it consolidates:**
```cypher
MATCH (rollup:ProblemAwarenessStrategy {node_id: $rollup_id})
WHERE rollup.node_id STARTS WITH 'rollup_'
MATCH (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual:ProblemAwarenessStrategy)
RETURN rollup, collect(individual) as individual_strategies
```

**List only rollup strategies (exclude individuals):**
```cypher
MATCH (strategy:ProblemAwarenessStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
WHERE strategy.node_id STARTS WITH 'rollup_'
RETURN strategy
```

**List only individual strategies (exclude rollups):**
```cypher
MATCH (strategy:ProblemAwarenessStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
WHERE NOT strategy.node_id STARTS WITH 'rollup_'
RETURN strategy
```