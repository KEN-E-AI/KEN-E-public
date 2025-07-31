/**
 * Types for news and social media monitoring feature
 */

export interface CompetitorEntry {
  name: string;
  website?: string;
  keywords: string[];
}

export interface MonitoringTopics {
  account_id: string;
  organization_id: string;
  industry_keywords: string[];
  company_keywords: string[];
  customer_keywords: string[];
  competitor_entries: CompetitorEntry[];
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
