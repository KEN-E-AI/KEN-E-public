# Knowledge Graph Design: Business Strategy

## 1\. Executive Summary

This document details the design for integrating a user's own business strategy into the knowledge graph.

## 2\. Updated Pydantic Model

UPDATE IN FILE: app/adk/agents/strategy\_agent/agents.py

```python
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Base Component Models ---
# These models represent the granular nodes in our knowledge graph.

class SWOTItem(BaseModel):
    """Represents a single Strength, Weakness, Opportunity, or Risk."""
    id: str = Field(..., description="A unique identifier for the item (e.g., 'strength-brand-reputation', 'risk-new-competitor').")
    description: str = Field(..., description="A clear and concise description of the SWOT item.")

class ValueProposition(BaseModel):
    """Represents a core value proposition of a product or service."""
    id: str = Field(..., description="A unique identifier (e.g., 'valueprop-ease-of-use').")
    display_name: str = Field(..., description="A short, human-readable name (e.g., 'Superior Ease of Use').")
    description: str = Field(..., description="A detailed explanation of the value proposition.")

class ProductService(BaseModel):
    """Details a specific product or service offered by the company."""
    id: str = Field(..., description="A unique identifier for the product (e.g., 'product-main-platform').")
    display_name: str = Field(..., description="The name of the product or service.")
    description: str = Field(..., description="A summary of the product's features and purpose.")
    value_propositions: List[ValueProposition] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="The 1-5 core value propositions this product delivers."
    )

class ProductCategory(BaseModel):
    """A category of products offered by the company."""
    category_name: str = Field(..., description="The name of the product category (e.g., 'Cloud Services', 'Consumer Electronics').")
    value_propositions: List[ValueProposition] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="The 1-5 core value propositions delivered by the products in this category."
    )
    products: List[ProductService] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 products within this category."
    )

class IndustryTrend(BaseModel):
    """Represents a significant trend affecting the industry."""
    id: str = Field(..., description="A unique identifier for the trend (e.g., 'trend-ai-in-analytics').")
    display_name: str = Field(..., description="A short name for the trend.")
    description: str = Field(..., description="A detailed description of the trend and its implications.")

class StrategicGoal(BaseModel):
    """A strategic goal for the business."""
    id: str = Field(..., description="A unique identifier for the goal (e.g., 'goal-increase-smb-market-share').")
    display_name: str = Field(..., description="A clear, concise statement of the goal.")
    description: str = Field(..., description="More detailed context about the goal.")

# --- Section Models ---
# These models group the components into the logical sections of the analysis.

class StrengthOpportunityLink(BaseModel):
    """Links a specific strength to one or more opportunities it enables."""
    strength: SWOTItem = Field(..., description="The specific internal strength.")
    linked_opportunities: List[SWOTItem] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 external opportunities that can be exploited by this strength."
    )

class WeaknessRiskLink(BaseModel):
    """Links a specific weakness to one or more risks it exposes the business to."""
    weakness: SWOTItem = Field(..., description="The specific internal weakness.")
    linked_risks: List[SWOTItem] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 external risks that are exacerbated by this weakness."
    )

class SWOTAnalysis(BaseModel):
    """A strategic planning tool to identify internal strengths/weaknesses and external opportunities/risks."""
    strengths_and_opportunities: List[StrengthOpportunityLink] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Identify 1-5 core internal strengths (e.g., strong brand, unique tech) and link each to the external opportunities it unlocks (e.g., new markets, favorable trends)."
    )
    weaknesses_and_risks: List[WeaknessRiskLink] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Identify 1-5 key internal weaknesses (e.g., high debt, outdated tech) and link each to the external risks it exposes the business to (e.g., new competitors, changing regulations)."
    )

# --- Main Model ---
# This is the new top-level model that replaces the old narrative-based one.

class StructuredBusinessStrategy(BaseModel):
    """
    Defines the structured output for a comprehensive business strategy document,
    designed for direct ingestion into a knowledge graph.
    """
    company_name: str = Field(..., description="The official name of the company being analyzed.")
    company_overview_summary: str = Field(..., description="A comprehensive narrative that introduces the company's identity and background.")
    business_value_propositions: List[ValueProposition] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 core value propositions that describe the business as a whole and how it creates value for its customers."
    )
    product_portfolio: List[ProductCategory] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 key product categories, each containing 1-5 flagship products/services."
    )
    swot_analysis: SWOTAnalysis
    strategic_goals: List[StrategicGoal] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 highest-level strategic goals that must be met to maintain and improve the health of the business."
    )
    final_summary: str = Field(..., description="A high-level summary of the company's situation and key recommendations, written last.")
```

### Account Node

This will be the central node representing the user's own company.

**Account**
**Purpose**: To serve as the primary anchor for all account-specific strategic information. This node distinguishes the user's data from competitor data.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the account. Generated by the system when an account is created. | `acc_c6051eee55b647ab81a80ffab37295e2` |
| account\_name | string | The friendly name for the account. Generated by the user when creating or editing the account. | `KEN-E` |
| data\_region | string | The location where the account’s data is stored. Any related GCS buckets or BigQuery datasets will only exist in the selected regions. Set by the user when creating the account. | `United States` |
| industry | string | The industry that best describes the market where the account operates and competes. Set by the user when creating the account. | `Professional, Scientific, and Technical Services [B2B]` |
| organization\_id | string | A unique identifier for the parent organization. Generated by the system when the organization is created. | `org_4708c246097141b3b5adf4b67c1b41f7` |
| label | string | The node type in neo4j. | `Account` |
| customer\_regions | list | The primary regions where the company’s customers live. This field is used for identifying regional holidays. Set by the user when creating or editing the account. | `["US"]` |
| status | string | Set to “Inactive” to disable all token usage. | `Active` |
| timezone | string | The timezone that should be applied when generating reports. Set by the user when generating or editing the account. | `America/New_York` |
| websites | list | A list of websites owned by the company. KEN-E will study these to create the account knowledge graph. Set by the user when generating or editing an account. | `["https://ken-e.ai"]` |
| company\_overview | string | A narrative that introduces the company's identity and background (founding details, major milestones, evolution), its mission, vision, and values, an overview of its leadership and organizational structure, and its brand identity and customer base. Generated by the strategy agents when the account is created. | `KEN-E was founded in 2025 as a…` |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Account | `-[:BELONGS_TO]->` | Organization | Each account will belong to exactly one organization. |
| Account | `-[:OPERATES_WITHIN]->` | GeographicRegion | Every Account must have the ‘OPERATES\_WITHIN’ relationship with exactly one geographic region inside of an industry. |
| Account | `-[:OPERATES_WITHIN]->` | CompetitiveEnvironment | |
| Account | `-[:OPERATES_ON]->` | BusinessModel | Explains how the business generates revenue and incurs costs. |
| Account | `-[:AFFECTED_BY_ANALYSIS]->` | SWOTAnalysis | The SWOT Analysis identifies strengths and weaknesses of the business, and then explores opportunities and risks that these might create. |
| Account | `-[:HAS_GOAL]->` | Goal | Define the strategic goals of the business. |
| Account | `-[:HAS_VALUE_PROPOSITION]->` | ValueProposition | Describes how the business generates value for customers. |
| Account | `-[:OFFERS_PRODUCTS]->` | ProductCategory | The high level categories of products or services offered by the business. |
| Account | `<-[:BELONGS_TO]-` | \<all child nodes\> | All child nodes of the Account are identified as describing the parent Account. |

### ProductCategory Node

**ProductCategory**
**Purpose**: The top 1-5 most important product categories are created by the strategy agent as ProductCategory nodes when the account is created. Others may be added over time.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the ProductCategory. Generated by the system when the node is created. | `productcat_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `ProductCategory` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| product\_name | string | The friendly name of the product category. | `Portable Purifiers` |
| description | string | The description of a group of products or services offered to customers. | `Small air purifiers for…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| ProductCategory | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| ProductCategory | `-[:INCLUDES_PRODUCT]->` | Product | The top products or services offered by the company are grouped under product categories. |
| ProductCategory | `-[:HAS_VALUE_PROPOSITION]->` | ValueProposition | Describes how the products or services within this category create value for customers. |
| ProductCategory | `-[:MEASURES_EFFECTIVENESS_WITH]->` | Metric | Identifies the metric that is used as a key performance indicator (KPI) to determine if the Product Category is effective at accomplishing its goal. |
| ProductCategory | `-[:MEASURES_EFFICIENCY_WITH]->` | Metric | Identifies the metric that is used as a key performance indicator (KPI) to determine if the Product Category is efficient at accomplishing its goal. |

### Product Node

**Product**
**Purpose**: The top 1-5 most important products/services within each product category are created by the strategy agent as Product nodes when the account is created. Others may be added over time.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the product. Generated by the system when a product node is created. | `prod_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Product` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| product\_name | string | The friendly name of the product. | `Intellipure Mini Air Purifier` |
| description | string | The product description. | `A small air purifier for…` |
| product\_detail\_page | string | (optional) The URL of the product detail page. | `https://www.example.com/product1` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Product | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Product | `-[:MAY_BE_SUBSTITUTED_FOR]->` | SubstituteProduct | A product or service offered by a competitor that may be seen by customers as a substitute for this product. |
| Product | `-[:HAS_VALUE_PROPOSITION]->` | ValueProposition | Describes how the product or service creates value for customers. |
| Product | `<-[:INCLUDES_PRODUCT]-` | ProductCategory | The top products or services offered by the company are grouped under product categories. |

### ValueProposition Node

**ValueProposition**
**Purpose**: To define why customers choose the user's products. This is a key element for strategic reasoning.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the value proposition. Generated by the system when a ValueProposition node is created. | `value_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `ValueProposition` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the value proposition in less than 60 characters. | `Quiet fan system` |
| description | string | The full description of a core value of the company's or the products/services it offers to customers. | `Our air purifier runs at very low…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| ValueProposition | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| ValueProposition | `<-[:HAS_VALUE_PROPOSITION]-` | Account | Describes how the business generates value for customers. |
| ValueProposition | `<-[:HAS_VALUE_PROPOSITION]-` | Product | Describes how the product or service creates value for customers. |
| ValueProposition | `<-[:HAS_VALUE_PROPOSITION]-` | ProductCategory | Describes how the products or services within this category create value for customers. |

### Strength Node

**Strength**
**Purpose**: To define strategies that capitalize on the company’s strengths.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Strength. Generated by the system when a Strength node is created. | `strength_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Strength` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the strength in less than 60 characters. | `Highly loyal customer base` |
| description | string | The full description of a top advantage that the company has over competitors. | `A key strength is the highly engaged…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Strength | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Strength | `<-[:HAS_STRENGTH]-` | SWOTAnalysis | Groups this strength with the other items included in the SWOT analysis. |
| Strength | `-[:CREATES]->` | Opportunity | Identifies an opportunity that may result from this strength. |

### Weakness Node

**Weakness**
**Purpose**: To define strategies that acknowledge the company’s weaknesses.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Weakness. Generated by the system when a Weakness node is created. | `weakness_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Weakness` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the weakness in less than 60 characters. | `High manufacturing cost` |
| description | string | The full description of an internal limitation that the company has when compared to competitors. | `A key weakness is the expensive materials…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Weakness | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Weakness | `<-[:HAS_WEAKNESS]-` | SWOTAnalysis | Groups this weakness with the other items included in the SWOT analysis. |
| Weakness | `-[:CREATES]->` | Risk | Identifies a risk that may result from this weakness. |

### Opportunity Node

**Opportunity**
**Purpose**: To define strategies that position the company to take advantage of market opportunities.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Opportunity. Generated by the system when a Opportunity node is created. | `opportunity_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Opportunity` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the opportunity in less than 60 characters. | `Changing customer preferences` |
| description | string | The full description of external chance for growth that the company might be able to take advantage of. | `Customers have increasingly began…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Opportunity | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Opportunity | `<-[:CREATES]-` | Strength | Identifies an opportunity that may result from this strength. |

### Risk Node

**Risk**
**Purpose**: To define risks that the company should avoid or be prepared for.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Threat. Generated by the system when a Threat node is created. | `threat_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Threat` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the threat in less than 60 characters. | `Well funded startup competitors` |
| description | string | The full description of an external factor that could cause harm to the company. | `Smaller and more nimble competitors…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Risk | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Risk | `<-[:CREATES]-` | Weakness | Identifies a risk that may result from this weakness. |

### Goal Node

**Goal**
**Purpose**: To make the company's strategy explicit and measurable.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Goal. Generated by the system when a Goal node is created. | `goal_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `Goal` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| display\_name | string | A short name to describe the goal in less than 60 characters. | `Increase Market Share in SMB Segment` |
| description | string | The full description of a specific, strategic objective the company aims to achieve. | `A key strategic objective is to grow…` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Goal | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| Goal | `<-[:HAS_GOAL]-` | Account | Identifies a strategic goal that this business must accomplish to be successful. |
| Goal | `-[:MEASURES_EFFECTIVENESS_WITH]->` | Metric | Identifies the metric that is used as a key performance indicator (KPI) to determine if the business is effective at accomplishing this goal. |
| Goal | `-[:MEASURES_EFFICIENCY_WITH]->` | Metric | Identifies the metric that is used as a key performance indicator (KPI) to determine if the business is efficient at accomplishing this goal. |

