# Knowledge Graph Design: Industry Strategy 

## 1. Executive Summary 

This document details the design for conducting research on an industry and adding findings to the knowledge graph.  This research should be refreshed periodically for each industry. 

See full diagram 

## 2. Pydantic Model 

NOT BUILD IN THE APP: This pydantic model is used to periodically refresh the industry strategies that are shared between all accounts operating within the same geographic region.  This model is not built directly into the application. 

```python
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Base Component Models ---
# These models represent the granular, reusable nodes in our knowledge graph that describe an entire industry.

class MarketOpportunity(BaseModel):
    """Represents an external chance for growth that companies operating within the industry and geographic region might take advantage of. Examples include unmet customer needs or gaps in the market available to all businesses within the industry."""
    id: str = Field(..., description="A unique identifier for the opportunity (e.g., 'opportunity-smb-ease-of-use').")
    display_name: str = Field(..., description="A short, human-readable name for the opportunity.")
    description: str = Field(..., description="A detailed description of the market opportunity.")

class MarketRisk(BaseModel):
    """Represents an external risk, potential threat or negative factor that companies operating within the industry and geographic region should avoid."""
    id: str = Field(..., description="A unique identifier for the risk (e.g., 'risk-data-privacy-regulation').")
    display_name: str = Field(..., description="A short, human-readable name for the risk.")
    description: str = Field(..., description="A detailed description of the market risk.")

class PESTELFactor(BaseModel):
    """Represents a single factor within the PESTEL analysis."""
    id: str = Field(..., description="A unique identifier for the factor (e.g., 'tech-ai-adoption').")
    description: str = Field(..., description="Details about the factor and its potential impact.")
    trend: str = Field(..., description="The direction of the trend's impact (e.g., 'Positive', 'Negative', 'Neutral').")
    opportunities_created: Optional[List[MarketOpportunity]] = Field(None, description="Opportunities that arise from this factor.")
    risks_created: Optional[List[MarketRisk]] = Field(None, description="Risks that arise from this factor.")

class PortersForce(BaseModel):
    """Represents the analysis of a single force in Porter's Five Forces."""
    level: str = Field(..., description="The assessed level of the force (e.g., 'High', 'Medium', 'Low').")
    description: str = Field(..., description="The reasoning and evidence behind the assessed level.")
    opportunities_created: Optional[List[MarketOpportunity]] = Field(None, description="Opportunities that arise from this force.")
    risks_created: Optional[List[MarketRisk]] = Field(None, description="Risks that arise from this force.")

class IndustryTrend(BaseModel):
    """Represents a market dynamic that might create an opportunity or threat for companies operating within the industry and geographic region."""
    id: str = Field(..., description="A unique identifier for the trend (e.g., 'trend-ai-in-analytics').")
    display_name: str = Field(..., description="A short name for the trend.")
    description: str = Field(..., description="A detailed description of the trend and its implications.")
    opportunities_created: List[MarketOpportunity] = Field(..., description="Opportunities that arise from this trend.")
    risks_created: List[MarketRisk] = Field(..., description="Risks that arise from this trend.")

class KeySuccessFactor(BaseModel):
    """Represents a critical capability required for companies within the industry and geographic region to succeed."""
    id: str = Field(..., description="A unique identifier (e.g., 'ksf-data-integration').")
    display_name: str = Field(..., description="A short, human-readable name for the KSF.")
    description: str = Field(..., description="An explanation of why this factor is critical in the market.")

# --- Section Models ---
# These models group the components into the logical sections of the analysis.

class PESTELAnalysis(BaseModel):
    """A structured representation of the PESTEL analysis for the industry. This analysis helps a company who operates within the industry and geographic region understand how external forces might impact its operations, strategy, and overall profitability."""
    political: List[PESTELFactor] = Field(..., description="Factors related to government policy, political stability, and trade or tax policies that can impact the industry.")
    economic: List[PESTELFactor] = Field(..., description="Macroeconomic factors such as economic growth, interest rates, exchange rates, and inflation that affect the industry.")
    social: List[PESTELFactor] = Field(..., description="Sociocultural factors including demographics, population growth, cultural norms, and consumer attitudes that influence the market.")
    technological: List[PESTELFactor] = Field(..., description="Factors related to innovation, research and development (R&D), automation, and technological awareness that can create or disrupt the industry.")
    environmental: List[PESTELFactor] = Field(..., description="Ecological and environmental factors such as weather, climate, environmental policies, and sustainability concerns that impact the industry.")
    legal: List[PESTELFactor] = Field(..., description="Factors related to laws and regulations, such as consumer protection, labor laws, intellectual property, and industry-specific regulations.")

class PortersFiveForcesAnalysis(BaseModel):
    """A structured representation of the Porter's Five Forces analysis for the industry. This analysis helps companies within the industry understand the competitive landscape and factors influencing profitability within the specific industry and geographic region."""
    threat_of_new_entrants: PortersForce = Field(..., description="Assesses how easily new competitors can enter the market, considering barriers like economies of scale, brand loyalty, and capital requirements.")
    bargaining_power_of_suppliers: PortersForce = Field(..., description="Evaluates the power of suppliers to drive up the prices of materials or services, influenced by the number of suppliers and the uniqueness of their offerings.")
    intensity_of_competitive_rivalry: PortersForce = Field(..., description="Analyzes the level of competition among existing firms in the industry, considering factors like the number of competitors and industry growth rate.")
    threat_of_substitute_products: PortersForce = Field(..., description="Measures the likelihood of customers finding a different way of doing what the industry's product or service does.")
    bargaining_power_of_buyers: PortersForce = Field(..., description="Assesses the power of customers to drive down prices, influenced by the number of buyers and their sensitivity to price.")

# --- Main Model ---
# This is the new top-level model for a comprehensive industry analysis.

class StructuredIndustryAnalysis(BaseModel):
    """
    Defines the structured output for a comprehensive industry analysis document,
    designed for direct ingestion into a knowledge graph.
    """
    industry_name: str = Field(..., description="The display name for the industry, e.g., 'B2B SaaS Analytics Industry'.")
    industry_description: str = Field(..., description="A narrative overview of the industry.")
    key_success_factors: List[KeySuccessFactor]
    industry_trends: List[IndustryTrend]
    porters_five_forces: PortersFiveForcesAnalysis
    pestel_analysis: PESTELAnalysis
```



## 3. Industry Nodes 

### Industry Node 

Represents an industry where the business might operate.  Industries are predefined and selected during account creation.  All accounts must be linked to exactly one industry node. 

**Industry**
**Purpose**: To serve as the primary anchor for all industry-specific strategic information.  This node and its children contain information that is shared between all accounts that operate within the industry. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Industry. Generated by the system when an Industry node is created.  | `industry_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `Industry`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the industry in less than 60 characters.  | `Construction`  |
| description | string | The full description of the industry.  | `Building, repairing and renovating…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| Industry | `<-[:OPERATES_WITHIN]-` | GeographicRegion | Every GeographicRegion must have the ‘OPERATES\_WITHIN’ relationship with exactly one industry.  |

### GeographicRegion Node 

Represents a geographic region within an industry.  The geographic region is selected during account creation.  All accounts must be linked to exactly one GeographicRegion node to indicate the combination of industry and region where they operate. 

**GeographicRegion**
**Purpose**: To serve as the primary anchor for all strategic information that is specific to the industry and geographic region.  This node and its children contain information that is shared between all accounts that operate within the industry. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Industry. Generated by the system when an Industry node is created.  | `industry_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `GeographicRegion`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the industry in less than 60 characters.  | `North America`  |
| description | string | The full description of the geographic region and how it is defined.  | `Building, repairing and renovating…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| GeographicRegion | `<-[:OPERATES_WITHIN]-` | Account | Every Account must have the ‘OPERATES\_WITHIN’ relationship with exactly one industry.  |
| GeographicRegion | `-[:AFFECTED_BY_ANALYSIS]->` | PESTELAnalysis | The PESTEL Analysis should be conducted periodically for each industry.  |
| GeographicRegion | `-[:AFFECTED_BY_ANALYSIS]->` | PortersFiveForcesAnalysis | The Porter’s Five Forces Analysis should be conducted periodically for each industry.  |
| GeographicRegion | `-[:IS_CHARACTERIZED_BY]->` | IndustryTrend | The market dynamics that create opportunities or threats for companies operating within the industry.  |
| GeographicRegion | `-[:REQUIRES_CAPABILITY]->` | KeySuccessFactor | The critical capabilities required by businesses operating within this industry to succeed.  |

### IndustryTrend Node 

**IndustryTrend**
**Purpose**: To capture market dynamics that create opportunities or threats. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the IndustryTrend. Generated by the system when an IndustryTrend node is created.  | `trend_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `IndustryTrend`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the industry trend in less than 60 characters.  | `AI Integration with Analytics`  |
| description | string | The full description of a market dynamic that might create an opportunity or threat for companies operating within the industry and geographic region.  | `A growing trend where customers…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| IndustryTrend | `<-[:IS_CHARACTERIZED_BY]-` | GeographicRegion | Every IndustryTrend describes an industry operating with a specific geographic region.  |
| IndustryTrend | `-[:CREATES]->` | MarketOpportunity | IndustryTrends create opportunities that companies can take advantage of.  |
| IndustryTrend | `-[:CREATES]->` | MarketRisk | IndustryTrends create risks that companies should avoid.  |

### KeySuccessFactor Node 

**KeySuccessFactor**
**Purpose**: To define the critical capabilities that are required to succeed in this industry. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the MarketRisk. Generated by the system when a MarketRisk node is created.  | `marketrisk_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `KeySuccessFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the market risk in less than 60 characters.  | `Differentiated products`  |
| description | string | The full description of a critical capability required by companies within the geographic region who compete within the industry to succeed in the market.  | `Successful companies in this industry…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| KeySuccessFactor | `<-[:REQUIRES_CAPABILITY]-` | GeographicRegion | Identifies the critical capabilities required for companies within the industry and geographic region to succeed.  |

### MarketOpportunity Node 

**MarketOpportunity**
**Purpose**: To define strategies that position the company to take advantage of market opportunities. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the Opportunity. Generated by the system when a Opportunity node is created.  | `marketopp_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `MarketOpportunity`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the market opportunity in less than 60 characters.  | `Changing customer preferences`  |
| description | string | The full description of an external chance for growth that companies operating within the industry and geographic region might take advantage of. Examples include unmet customer needs or gaps in the market available to all businesses within the industry.  | `Customers have increasingly began…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| MarketOpportunity | `<-[:CREATES]-` | IndustryTrend | Identifies opportunities created by industry trends.  |
| MarketOpportunity | `<-[:CREATES]-` | PoliticalFactor | Identifies opportunities created by external political factors.  |
| MarketOpportunity | `<-[:CREATES]-` | EnvironmentalFactor | Identifies opportunities created by external environmental factors.  |
| MarketOpportunity | `<-[:CREATES]-` | TechnologicalFactor | Identifies opportunities created by external technological factors.  |
| MarketOpportunity | `<-[:CREATES]-` | SocialFactor | Identifies opportunities created by external social factors.  |
| MarketOpportunity | `<-[:CREATES]-` | EconomicFactor | Identifies opportunities created by external economic factors.  |
| MarketOpportunity | `<-[:CREATES]-` | LegalFactor | Identifies opportunities created by external legal factors.  |
| MarketOpportunity | `<-[:CREATES]-` | ThreatOfNewEntrants | Identifies opportunities created by the threat of new entrants.  |
| MarketOpportunity | `<-[:CREATES]-` | BargainingPowerOfSuppliers | Identifies opportunities created by the bargaining power of suppliers.  |
| MarketOpportunity | `<-[:CREATES]-` | CompetitiveRivalry | Identifies opportunities created by competitive rivalry.  |
| MarketOpportunity | `<-[:CREATES]-` | ThreatOfSubstitutes | Identifies opportunities created by the threat of substitutes.  |
| MarketOpportunity | `<-[:CREATES]-` | BargainingPowerOfBuyers | Identifies opportunities created by the bargaining power of buyers.  |

### MarketRisk Node 

**MarketRisk**
**Purpose**: To define strategies that position the company to avoid risks in the market. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the MarketRisk. Generated by the system when a MarketRisk node is created.  | `marketrisk_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `MarketRisk`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the market risk in less than 60 characters.  | `Changing customer preferences`  |
| description | string | The full description of an external risk, potential threat or negative factor that companies operating within the industry and geographic region should avoid.  | `Customers have increasingly began…`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| MarketRisk | `<-[:CREATES]-` | IndustryTrend | Identifies risks created by industry trends.  |
| MarketRisk | `<-[:CREATES]-` | PoliticalFactor | Identifies risks created by external political factors.  |
| MarketRisk | `<-[:CREATES]-` | EnvironmentalFactor | Identifies risks created by external environmental factors.  |
| MarketRisk | `<-[:CREATES]-` | TechnologicalFactor | Identifies risks created by external technological factors.  |
| MarketRisk | `<-[:CREATES]-` | SocialFactor | Identifies risks created by external social factors.  |
| MarketRisk | `<-[:CREATES]-` | EconomicFactor | Identifies risks created by external economic factors.  |
| MarketRisk | `<-[:CREATES]-` | LegalFactor | Identifies risks created by external legal factors.  |
| MarketRisk | `<-[:CREATES]-` | ThreatOfNewEntrants | Identifies risks created by the threat of new entrants.  |
| MarketRisk | `<-[:CREATES]-` | BargainingPowerOfSuppliers | Identifies risks created by the bargaining power of suppliers.  |
| MarketRisk | `<-[:CREATES]-` | CompetitiveRivalry | Identifies risks created by competitive rivalry.  |
| MarketRisk | `<-[:CREATES]-` | ThreatOfSubstitutes | Identifies risks created by the threat of substitutes.  |
| MarketRisk | `<-[:CREATES]-` | BargainingPowerOfBuyers | Identifies risks created by the bargaining power of buyers.  |

### PESTELAnalysis Node 

**PESTELAnalysis**
**Purpose**: The central anchor for the PESTEL analysis nodes.  This analysis helps a company understand how external forces might impact its operations, strategy, and overall profitability. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the PESTELAnalysis. Generated by the system when a PESTELAnalysis node is created.  | `pestel_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `PESTELAnalysis`  |
| display\_name | string | A short name to describe the PESTEL Analysis in less than 60 characters.  | `PESTEL Analysis for B2B SaaS`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| PESTELAnalysis | `<-[:AFFECTED_BY_ANALYSIS]-` | GeographicRegion | This analysis helps companies within the industry and geographic region understand how external forces might impact its operations, strategy, and overall profitability.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | PoliticalFactor | Factors related to government policy, political stability, and trade or tax policies that can impact the industry.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | EnvironmentalFactor | Ecological and environmental factors such as weather, climate, environmental policies, and sustainability concerns that impact the industry.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | TechnologicalFactor | Factors related to innovation, research and development (R\&D), automation, and technological awareness that can create or disrupt the industry.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | SocialFactor | Sociocultural factors including demographics, population growth, cultural norms, and consumer attitudes that influence the market.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | EconomicFactor | Macroeconomic factors such as economic growth, interest rates, exchange rates, and inflation that affect the industry.  |
| PESTELAnalysis | `-[:INCLUDES_FACTOR]->` | LegalFactor | Factors related to laws and regulations, such as consumer protection, labor laws, intellectual property, and industry-specific regulations.  |

### PoliticalFactor Node 

**PoliticalFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating the government policies, tax policies, trade restrictions, labor laws, and political stability that may influence businesses within the industry and geographic region. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the PoliticalFactor. Generated by the system when a PoliticalFactor node is created.  | `politicalfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `PoliticalFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| PoliticalFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Factors related to government policy, political stability, and trade or tax policies that can impact the industry.  |
| PoliticalFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external political factors.  |
| PoliticalFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external political factors.  |

### EconomicFactor Node 

**EconomicFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating the economic growth, interest rates, inflation, unemployment rates, and disposable income of the consumers within the geographic region. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the EconomicFactor. Generated by the system when an EconomicFactor node is created.  | `economicfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `EconomicFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| EconomicFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Ecological and environmental factors such as weather, climate, environmental policies, and sustainability concerns that impact the industry.  |
| EconomicFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external economic factors.  |
| EconomicFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external economic factors.  |

### SocialFactor Node 

Identifies the demographics, cultural trends, consumer attitudes, buying habits, and living standards that may influence business performance. 

**SocialFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating the demographics, cultural trends, consumer attitudes, buying habits, and living standards that may influence business performance in the industry and geographic region. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the SocialFactor. Generated by the system when a SocialFactor node is created.  | `socialfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `SocialFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| SocialFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Sociocultural factors including demographics, population growth, cultural norms, and consumer attitudes that influence the market.  |
| SocialFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external social factors.  |
| SocialFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external social factors.  |

### TechnologicalFactor Node 

Identifies the advancements in technology, innovation, the rate of technological change, and their impact on the company’s products, services, and processes. 

**TechnologicalFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating the impact of technology, innovation, the rate of technological change on the products, services, and processes of companies who operate within the industry and geographic region. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the TechnologicalFactor. Generated by the system when a TechnologicalFactor node is created.  | `technologicalfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `TechnologicalFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| TechnologicalFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Factors related to innovation, research and development (R\&D), automation, and technological awareness that can create or disrupt the industry.  |
| TechnologicalFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external technological factors.  |
| TechnologicalFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external technological factors.  |

### EnvironmentalFactor Node 

Identifies factors such as climate change, environmental laws, sustainability, waste disposal, and the impact of human activities on the environment. 

**EnvironmentalFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating factors such as climate change, environmental laws, sustainability, waste disposal, and the impact of human activities on the environment. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the EnvironmentalFactor. Generated by the system when a EnvironmentalFactor node is created.  | `environmentalfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `EnvironmentalFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| EnvironmentalFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Ecological and environmental factors such as weather, climate, environmental policies, and sustainability concerns that impact the industry.  |
| EnvironmentalFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external environmental factors.  |
| EnvironmentalFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external environmental factors.  |

### LegalFactor Node 

**LegalFactor**
**Purpose**: To help a company identify opportunities and risks by evaluating the applicable laws and regulations, including anti-competition laws, labor laws, product safety regulations, and environmental laws that may influence the behavior of businesses that operate within this industry around the world. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the LegalFactor. Generated by the system when a LegalFactor node is created.  | `legalfactor_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `LegalFactor`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the political factor in less than 60 characters.  | `Proposed changes to tax policy`  |
| trend | string | Set to "Positive" to indicate that the factor is likely to be helpful to the business, or "Negative" to indicate that the factor is likely to be harmful to the business.  | `Positive`  |
| description | string | A description of the factor as well as the evidence that it might have a positive or negative impact on the business.  | `The growing adoption of AI in business decision-making increases the demand for intelligent analytics platforms.`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| LegalFactor | `<-[:INCLUDES_FACTOR]-` | PESTELAnalysis | Factors related to laws and regulations, such as consumer protection, labor laws, intellectual property, and industry-specific regulations.  |
| LegalFactor | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by external legal factors.  |
| LegalFactor | `-[:CREATES]->` | MarketRisk | Identifies risks created by external legal factors.  |

### PortersFiveForcesAnalysis Node 

**PortersFiveForcesAnalysis**
**Purpose**: The central anchor node for the Porter’s Five Forces Analysis.  This analysis helps companies within the industry understand the competitive landscape and factors influencing profitability within the specific industry and geographic region. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| portersanalysis\_id | string | A unique identifier for the PortersFiveForcesAnalysis. Generated by the system when a PortersFiveForcesAnalysis node is created.  | `porters_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `PortersFiveForcesAnalysis`  |
| display\_name | string | A short name to describe the Porters 5 Forces Analysis in less than 60 characters.  | `Porters 5 Forces Analysis for Construction`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| PortersFiveForcesAnalysis | `<-[:AFFECTED_BY_ANALYSIS]-` | GeographicRegion | This analysis helps companies within the industry understand the competitive landscape and factors influencing profitability within the specific industry and geographic region.  |
| PortersFiveForcesAnalysis | `-[:INCLUDES_FORCE]->` | ThreatOfNewEntrants | A detailed description of how easy or difficult it is for new competitors to enter the market within the given geographic region.  |
| PortersFiveForcesAnalysis | `-[:INCLUDES_FORCE]->` | BargainingPowerOfSuppliers | A detailed description of how much power suppliers have to raise their prices or reduce the quality of their goods and services within the given geographic region.  |
| PortersFiveForcesAnalysis | `-[:INCLUDES_FORCE]->` | CompetitiveRivalry | A detailed description of the intensity of competition among existing firms in an industry and geographic region.  |
| PortersFiveForcesAnalysis | `-[:INCLUDES_FORCE]->` | ThreatOfSubstitutes | A detailed description of the potential for products or services from other industries to fulfill the same customer needs within the given geographic region.  |
| PortersFiveForcesAnalysis | `-[:INCLUDES_FORCE]->` | BargainingPowerOfBuyers | A detailed description of the ability of customers to influence prices and terms within an industry and geographic region.  |

### ThreatOfNewEntrants Node 

**ThreatOfNewEntrants**
**Purpose**: To help companies operating within the industry understand the opportunities and risks that emerge from how easy or difficult it is for new competitors to enter a market. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| entrantsthreat\_id | string | A unique identifier for the ThreatOfNewEntrants. Generated by the system when a ThreatOfNewEntrants node is created.  | `entrantsthreat_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `ThreatOfNewEntrants`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the force in less than 60 characters.  | `High capital requirements`  |
| description | string | A detailed description of how easy or difficult it is for new competitors to enter the market within the given geographic region. High barriers to entry, such as significant capital requirements, brand loyalty, or government regulations, reduce this threat, making the industry more attractive for established firms.  | `The growing adoption of AI in...`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| ThreatOfNewEntrants | `<-[:INCLUDES_FORCE]-` | PortersFiveForcesAnalysis | A detailed description of how easy or difficult it is for new competitors to enter the market within the given geographic region.  |
| ThreatOfNewEntrants | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by the threat of new entrants.  |
| ThreatOfNewEntrants | `-[:CREATES]->` | MarketRisk | Identifies risks created by the threat of new entrants.  |

### BargainingPowerOfSuppliers Node 

**BargainingPowerOfSuppliers**
**Purpose**: To help companies operating within the industry understand the opportunities and risks that emerge from the power of suppliers to raise prices or reduce quality of goods and services. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| supplierpower\_id | string | A unique identifier for the BargainingPowerOfSuppliers. Generated by the system when a BargainingPowerOfSuppliers node is created.  | `supplierpower_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `BargainingPowerOfSuppliers`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the force in less than 60 characters.  | `High capital requirements`  |
| description | string | A detailed description of how much power suppliers have to raise their prices or reduce the quality of their goods and services within the given geographic region. Factors like the number of suppliers and the uniqueness of their offerings influence this power.  | `The growing adoption of AI in...`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| BargainingPowerOfSuppliers | `<-[:INCLUDES_FORCE]-` | PortersFiveForcesAnalysis | A detailed description of how much power suppliers have to raise their prices or reduce the quality of their goods and services within the given geographic region.  |
| BargainingPowerOfSuppliers | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by the bargaining power of suppliers.  |
| BargainingPowerOfSuppliers | `-[:CREATES]->` | MarketRisk | Identifies risks created by the bargaining power of suppliers.  |

### CompetitiveRivalry Node 

**CompetitiveRivalry**
**Purpose**: To help companies operating within the industry understand the opportunities and risks that emerge from the intensity of competition among existing firms in an industry. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| entrantsthreat\_id | string | A unique identifier for the ThreatOfNewEntrants. Generated by the system when a ThreatOfNewEntrants node is created.  | `entrantsthreat_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `ThreatOfNewEntrants`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the force in less than 60 characters.  | `High capital requirements`  |
| description | string | A detailed description of the intensity of competition among existing firms in an industry and geographic region. High rivalry, often characterized by many competitors, slow industry growth, and similar products, can lead to lower profitability as firms engage in price wars and other competitive actions.  | `The growing adoption of AI in...`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| CompetitiveRivalry | `<-[:INCLUDES_FORCE]-` | PortersFiveForcesAnalysis | A detailed description of the intensity of competition among existing firms in an industry and geographic region.  |
| CompetitiveRivalry | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by competitive rivalry.  |
| CompetitiveRivalry | `-[:CREATES]->` | MarketRisk | Identifies risks created by competitive rivalry.  |

### ThreatOfSubstitutes Node 

**ThreatOfSubstitutes**
**Purpose**: To help companies operating within the industry understand the opportunities and risks that emerge from the potential for products or services from other industries to fulfill the same customer needs. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| substitutethreat\_id | string | A unique identifier for the ThreatOfSubstitutes. Generated by the system when a ThreatOfSubstitutes node is created.  | `substitutethreat_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `ThreatOfSubstitutes`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the force in less than 60 characters.  | `High capital requirements`  |
| description | string | A detailed description of the potential for products or services from other industries to fulfill the same customer needs within the given geographic region. A high threat of substitutes can limit pricing power and reduce profitability for existing firms.  | `The growing adoption of AI in...`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| ThreatOfSubstitutes | `<-[:INCLUDES_FORCE]-` | PortersFiveForcesAnalysis | A detailed description of the potential for products or services from other industries to fulfill the same customer needs within the given geographic region.  |
| ThreatOfSubstitutes | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by the threat of substitutes.  |
| ThreatOfSubstitutes | `-[:CREATES]->` | MarketRisk | Identifies risks created by the threat of substitutes.  |

### BargainingPowerOfBuyers Node 

This force looks at the ability of customers to influence prices and terms within an industry.  Buyers have significant power when they are concentrated, purchase in large volumes, or can easily switch to competitor offerings. 

**BargainingPowerOfBuyers**
**Purpose**: To help companies operating within the industry understand the opportunities and risks that emerge from the ability of customers to influence prices and terms within an industry. 

| name | type | description | example |
| :--- | :--- | :--- | :--- |
| buyerpower\_id | string | A unique identifier for the BargainingPowerOfBuyers. Generated by the system when a BargainingPowerOfBuyers node is created.  | `buyerpower_c6051eee55b647ab81a80ffab37295e2`  |
| label | string | The node type in neo4j.  | `BargainingPowerOfBuyers`  |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool.  | `Strategy`  |
| display\_name | string | A short name to describe the force in less than 60 characters.  | `High capital requirements`  |
| description | string | A detailed description of the ability of customers to influence prices and terms within an industry and geographic region. Buyers have significant power when they are concentrated, purchase in large volumes, or can easily switch to competitor offerings.  | `The growing adoption of AI in...`  |
| created\_time | timestamp | The timestamp when the node was created.  | 2025-07-29 22:06:45.928000 UTC  |
| last\_modified | timestamp | The timestamp when the node was last modified  | 2025-07-29 22:06:45.928000 UTC  |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated.  | `System generated`  |
| last\_modified\_by | string | Identifies the user who last modified the node.  | `John Doe`  |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created.  | |

**Relationships** 

| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| BargainingPowerOfBuyers | `<-[:INCLUDES_FORCE]-` | PortersFiveForcesAnalysis | A detailed description of the ability of customers to influence prices and terms within an industry and geographic region.  |
| BargainingPowerOfBuyers | `-[:CREATES]->` | MarketOpportunity | Identifies opportunities created by the bargaining power of buyers.  |
| BargainingPowerOfBuyers | `-[:CREATES]->` | MarketRisk | Identifies risks created by the bargaining power of buyers.  |