/**
 * Types for news and social media monitoring feature
 */

export interface CompetitorEntry {
  node_id?: string;
  name?: string; // DEPRECATED: Legacy field for backward compatibility
  website?: string;
  keywords: string[];
}

export interface CustomerProfileEntry {
  node_id?: string;
  name?: string; // DEPRECATED: Legacy field for backward compatibility
  keywords: string[];
}

export type ConceptType =
  | "company"
  | "location"
  | "topic"
  | "person"
  | "product"
  | "event"
  | "other";

export interface ConceptReference {
  url: string;
  title: string;
  description: string;
  sourceType: "wikipedia" | "wikidata" | "official_website" | "gemini_search";
}

export interface ConceptOption {
  id: string;
  label: string;
  type: ConceptType;
  description: string;
  reference: ConceptReference;
  confidenceScore: number;
}

export interface CustomerKeywordConcept {
  keyword: string;
  conceptId: string;
  conceptType: ConceptType;
  reference: ConceptReference;
  addedBy: string;
  addedAt: string;
}

export interface MonitoringTopics {
  account_id: string;
  organization_id: string;
  industry_keywords: string[];
  company_keywords: string[];
  customer_keywords: string[];
  customer_concepts?: CustomerKeywordConcept[];
  competitor_entries: CompetitorEntry[];
  customer_profile_entries: CustomerProfileEntry[];
  created_at: string;
  updated_at: string;
}

export interface IndustryKeywords {
  industry: string;
  keywords: string[];
  updated_by: string;
  updated_at: string;
}

export interface MonitoringResult {
  article_id: string;
  url: string;
  title: string;
  discovered_date: string;
  matched_topics: string[];
  accounts: string[];
  metadata: {
    source: string;
    published_date?: string;
    author?: string;
  };
}

export interface UpdateCompanyKeywordsRequest {
  account_id: string;
  company_keywords: string[];
}

export interface UpdateCustomerKeywordsRequest {
  account_id: string;
  customer_keywords: string[];
}

export interface AddCustomerConceptRequest {
  account_id: string;
  keyword: string;
  concept_id: string;
  concept_type: ConceptType;
  reference: ConceptReference;
}

export interface AddCompetitorRequest {
  account_id: string;
  name: string;
  website?: string;
  keywords: string[];
}

export interface UpdateCompetitorRequest {
  account_id: string;
  competitor_id: number;
  name?: string;
  website?: string;
  keywords?: string[];
}

export interface UpdateIndustryKeywordsRequest {
  industry: string;
  keywords: string[];
}
