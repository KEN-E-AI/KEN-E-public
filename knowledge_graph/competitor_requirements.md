# Knowledge Graph Design: Competitive Strategy

## Executive Summary

This document provides the definitive specification for modeling and ingesting competitive intelligence into the knowledge graph.

-----

## Updated Pydantic Model

UPDATE IN FILE: `app/adk/agents/strategy_agent/agents.py`

```python
from typing import List
from pydantic import BaseModel, Field, conlist

# -- REUSABLE & SUB-MODELS
class NamedDetail(BaseModel):
    """
    A generic model for an item that requires a short name and a
    longer, more detailed description.
    """
    name: str = Field(
        ...,
        description="A short, concise name or title for the item.",
        examples=["Brand Recognition", "Ease of Use"]
    )
    description: str = Field(
        ...,
        description="A longer, more detailed description of the item."
    )

class SubstituteProduct(BaseModel):
    """
    Defines a product or service from a competitor that can be
    seen as a substitute by customers.
    """
    name: str = Field(
        ...,
        description="The name of the substitute product or service.",
        examples=["Cloud Storage Pro", "Enterprise CRM Suite"]
    )
    description: str = Field(
        ...,
        description="A description of the product and its positioning in the market."
    )
    value_proposition: NamedDetail = Field(
        ...,
        description="The key value proposition that explains why a customer might choose this substitute product."
    )

# -- SWOT SUB-MODELS
class StrengthWithRisks(BaseModel):
    """
    Describes a competitor's strength and the corresponding risks (threats) it
    creates for your company.
    """
    name: str = Field(
        ...,
        description="A short, concise name for the competitor's strength.",
        examples=["Strong Distribution Network"]
    )
    description: str = Field(
        ...,
        description="A detailed description of the competitor's strength."
    )
    risks: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of risks created for your company as a result of the competitor's strength."
    )

class WeaknessWithOpportunities(BaseModel):
    """
    Describes a competitor's weakness and the corresponding opportunities it
    creates for your company.
    """
    name: str = Field(
        ...,
        description="A short, concise name for the competitor's weakness.",
        examples=["Poor Customer Support"]
    )
    description: str = Field(
        ...,
        description="A detailed description of the competitor's weakness."
    )
    opportunities: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of opportunities created for your company as a result of the competitor's weakness."
    )

# -- UPDATED COMPETITOR MODEL
class Competitor(BaseModel):
    """
    Holds detailed information about a single competitor, including a SWOT analysis.
    """
    name: str = Field(
        ...,
        description="The name of the competitor.",
        examples=["InnovateCorp", "Global Solutions Inc."]
    )
    description: str = Field(
        ...,
        description=(
            "A summary of the competitor, including their history, company size, "
            "revenue, pricing strategy, distribution channels, and brand positioning."
        )
    )
    value_propositions: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 key value propositions explaining why customers choose this competitor."
    )
    marketing_tactics: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 specific tactics the competitor uses to bring products to market, such as social media campaigns, cold emails, events, or ads.",
        examples=[
            {"name": "Social Media Campaigns", "description": "Runs targeted ad campaigns on Instagram and LinkedIn to reach young professionals."},
            {"name": "Content Marketing", "description": "Publishes weekly blog posts and a monthly newsletter on industry trends."}
        ]
    )
    substitute_products: conlist(SubstituteProduct, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 substitute products or services offered by the competitor."
    )
    strengths: conlist(StrengthWithRisks, min_length=1, max_length=10) = Field(
        ...,
        description="A SWOT analysis of the competitor's key strengths and the risks they pose."
    )
    weaknesses: conlist(WeaknessWithOpportunities, min_length=1, max_length=10) = Field(
        ...,
        description="A SWOT analysis of the competitor's weaknesses and the opportunities they create."
    )

# -- MAIN COMPETITIVE ANALYSIS MODEL
class CompetitiveAnalysis(BaseModel):
    """
    The main model to conduct a comprehensive competitive analysis for a business.
    """
    company_products: conlist(str, min_length=1, max_length=10) = Field(
        ...,
        description="A list of 1 to 10 of the company's top products or services being analyzed.",
        examples=["Cloud Storage Basic", "Cloud Analytics Dashboard"]
    )
    competitive_environment_description: str = Field(
        ...,
        description=(
            "A description of the competitive environment and the strategy used to identify competitors. This should evaluate geography, physical location, company size, brand awareness, target customer segments, and potential substitute products or services."
        )
    )
    competitors: conlist(Competitor, min_length=1, max_length=10) = Field(
        ...,
        description=(
            "A list of the top competitors. To identify them, determine the importance of geography "
            "and brand recognition in the market. Identify other businesses with products or services "
            "that may be seen as direct substitutes by the target market."
        )
    )
```

-----

## Competitive Nodes

### CompetitiveEnvironment Node

A central hub for all information related to the competitive strategy.

**Purpose**: To define a strategy that can be used to identify the company's competitors.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the CompetitiveEnvironment. Generated by the system when the node is created. | `competitiveenv_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `CompetitiveEnvironment` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **description** | string | The full description of the competitive environment and the strategy used to identify competitors. | `Key competitors will operate within…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **CompetitiveEnvironment** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **CompetitiveEnvironment** | \<-[:OPERATES\_WITHIN]- | Account | Every Account must have the ‘OPERATES\_WITHIN’ relationship with exactly one competitive environment node. |
| **CompetitiveEnvironment** | -[:IS\_KEY\_PLAYER]-\> | Competitor | Identifies the key competitors that operate within the competitive environment. |

-----

### Competitor Node

A central hub for all information related to a specific competitor.

**Purpose**: To define a strategy that can be used to identify the company's competitors.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the Competitor. Generated by the system when the node is created. | `competitor_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `Competitor` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short name of the competitor. | `Molekule, Inc` |
| **description** | string | A summary of the competitor, including their history, company size, revenue, pricing strategy, distribution channels, and brand positioning. | `This competitor will operate within…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **Competitor** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **Competitor** | -[:USES\_TACTIC]-\> | CompetitorTactic | Identifies a specific marketing tactic that the competitor uses to bring products to market. |
| **Competitor** | -[:HAS\_STRENGTH]-\> | CompetitorStrength | Identifies a key strength of the competitor that may create risk for the company. |
| **Competitor** | -[:HAS\_WEAKNESS]-\> | CompetitorWeakness | Identifies a key weakness of the competitor that may create opportunity for the company. |
| **Competitor** | -[:HAS\_VALUE\_PROPOSITION]-\> | ValueProposition | Explains why customers may choose to purchase products or services from this competitor. |
| **Competitor** | -[:OFFERS\_PRODUCT]-\> | SubstituteProduct | Identifies a product or service offered by the competitor that may be viewed as a substitute for a product or service offered by the company. |

-----

### CompetitorStrength Node

**Purpose**: To identify the strengths of key competitors.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the CompetitorStrength. Generated by the system when the node is created. | `competitorstrength_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `CompetitorStrength` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short name of the competitor’s strength. | `Recognized brand` |
| **description** | string | A detailed description of a top advantage that the competitor has over others. | `Molekule has operated for over…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **CompetitorStrength** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **CompetitorStrength** | \<-[:HAS\_STRENGTH]- | Competitor | Identifies a key strength of the competitor that may create risk for the company. |
| **CompetitorStrength** | -[:CREATES]-\> | Risk | Identifies a risk created for the company by the strength of a competitor. |

-----

### CompetitorWeakness Node

**Purpose**: To identify the strengths of key competitors.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the CompetitorWeakness. Generated by the system when the node is created. | `competitorweakness_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `CompetitorWeakness` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short name of the competitor’s weakness. | `Outsourced product team` |
| **description** | string | A detailed description of the competitor’s weakness. | `Molekule has a reputation for poor…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **CompetitorWeakness** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **CompetitorWeakness** | \<-[:HAS\_WEAKNESS]- | Competitor | Identifies a key weakness of the competitor that may create opportunities for the company. |
| **CompetitorWeakness** | -[:CREATES]-\> | Opportunity | Identifies an opportunity created for the company by the weakness of a competitor. |

-----

### CompetitorTactic Node

**Purpose**: To identify the tactics used by competitors to bring products and services to market.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the CompetitorTactic. Generated by the system when the node is created. | `competitortactic_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `CompetitorTactic` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short name of the competitor’s tactic. | `Annual conference` |
| **description** | string | A detailed description of a tactic the competitor uses to bring products or services to market, such as social media campaigns, cold emails, events, or ads. | `The Clean Air Con is hosted…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **CompetitorTactic** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **CompetitorTactic** | \<-[:USES\_TACTIC]- | Competitor | Identifies a specific marketing tactic that the competitor uses to bring products to market. |

-----

### SubstituteProduct Node

**Purpose**: The top 1-10 products that compete as substitutes for products offered by the company.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the SubstituteProduct. Generated by the system when a product node is created. | `substituteproduct_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `SubstituteProduct` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **product\_name** | string | The friendly name of the substitute product. | `Molekule Mini Air Purifier` |
| **description** | string | The description of a product/service offered by a competitor that competes with a product/service offered by the company. | `A small air purifier for…` |
| **product\_detail\_page** | string | (optional) The URL of the product detail page. | `https://www.example.com/product1` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **SubstituteProduct** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **SubstituteProduct** | \<-[:OFFERS\_PRODUCT]- | Competitor | Identifies a product or service offered by the competitor that may be viewed as a substitute for a product or service offered by the company. |
| **SubstituteProduct** | \<-[:MAY\_BE\_SUBSTITUTED\_FOR]- | Product | Identifies a specific product or service offered by the competitor that might be viewed as a substitute for a specific product or service offered by the company. |
| **SubstituteProduct** | -[:HAS\_VALUE\_PROPOSITION]-\> | ValueProposition | Explains why customers may choose to purchase the substitute product or service offered by a competitor. |

-----

### ValueProposition Node

**Purpose**: To define why customers choose the substitute product.

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| **node\_id** | string | A unique identifier for the value proposition. Generated by the system when a ValueProposition node is created. | `value_c6051eee55b647ab81a80ffab37295e2` |
| **label** | string | The node type in neo4j. | `ValueProposition` |
| **label** | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| **display\_name** | string | A short name to describe the value proposition in less than 60 characters. | `Quiet fan system` |
| **description** | string | The full description of a core value of the company's or the products/services it offers to customers. | `Our air purifier runs at very low…` |
| **created\_time** | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| **last\_modified** | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| **created\_by** | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| **last\_modified\_by** | string | Identifies the user who last modified the node. | `John Doe` |
| **embedding** | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |

**Relationships**

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| **ValueProposition** | -[:BELONGS\_TO]-\> | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| **ValueProposition** | \<-[:HAS\_VALUE\_PROPOSITION]- | Competitor | Explains why customers may choose to purchase products or services from this competitor. |
| **ValueProposition** | \<-[:HAS\_VALUE\_PROPOSITION]- | SubstituteProduct | Explains why customers may choose to purchase the substitute product or service offered by a competitor. |