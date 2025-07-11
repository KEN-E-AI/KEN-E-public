/**
 * Utilities for transforming API insights data to frontend format
 */

export interface APIInsight {
  activity_id: string;
  metric_id: string;
  activity_log_id: string;
  relationship_type: "INFLUENCE_CONFIRMED" | "NO_INFLUENCE_CONFIRMED";
  direction: "positive" | "negative" | null;
  metric_verbose_name: string;
  related_dataset_products: string[];
  evidence: any; // Complex evidence object
  activity_description: string;
}

export interface APIInsightResponse {
  insights: APIInsight[];
  intuitions: any[];
  total: number;
}

export interface FrontendInsight {
  insight_id: string;
  description: string;
  evidence: string;
  date_range: {
    start: string;
    end: string;
  };
  confidence_level: "high" | "medium" | "low";
  category: string;
  impact: "positive" | "negative" | "neutral";
  // Store original API IDs for deletion
  _originalData: {
    activity_log_id: string;
    metric_id: string;
  };
}

/**
 * Transform API insight data to frontend format
 */
export function transformAPIInsightToFrontend(apiInsight: APIInsight): FrontendInsight {
  // Generate a unique insight ID
  const insight_id = `${apiInsight.activity_log_id}_${apiInsight.metric_id}`;
  
  // Create human-readable description
  const description = createInsightDescription(apiInsight);
  
  // Extract and format evidence
  const evidence = extractEvidenceText(apiInsight.evidence);
  
  // Determine confidence level from evidence
  const confidence_level = determineConfidenceLevel(apiInsight);
  
  // Categorize based on activity and metric
  const category = categorizeInsight(apiInsight);
  
  // Determine impact from relationship type and direction
  const impact = determineImpact(apiInsight);
  
  // Create date range (using current dates as placeholder since API doesn't provide them)
  const date_range = createDateRange();

  return {
    insight_id,
    description,
    evidence,
    date_range,
    confidence_level,
    category,
    impact,
    _originalData: {
      activity_log_id: apiInsight.activity_log_id,
      metric_id: apiInsight.metric_id,
    },
  };
}

/**
 * Create human-readable description from API insight
 */
function createInsightDescription(apiInsight: APIInsight): string {
  const direction = apiInsight.direction || "neutral";
  const relationshipType = apiInsight.relationship_type === "INFLUENCE_CONFIRMED" ? "influenced" : "did not influence";
  
  return `Activity "${apiInsight.activity_description}" ${relationshipType} metric "${apiInsight.metric_verbose_name}" in a ${direction} direction.`;
}

/**
 * Extract evidence text from complex evidence object
 */
function extractEvidenceText(evidence: any): string {
  if (!evidence) {
    return "No evidence data available.";
  }

  let evidenceText = "";
  
  // Extract active evidence
  if (evidence.active_evidence) {
    if (evidence.active_evidence.evidence && Array.isArray(evidence.active_evidence.evidence)) {
      evidenceText += "Active Evidence:\n";
      evidenceText += evidence.active_evidence.evidence.join("\n");
      evidenceText += "\n\n";
    }
    if (evidence.active_evidence.data) {
      evidenceText += `Data: ${JSON.stringify(evidence.active_evidence.data, null, 2)}\n\n`;
    }
  }

  // Extract influence evidence
  if (evidence.influence_evidence) {
    evidenceText += "Influence Evidence:\n";
    evidenceText += `Influence likely: ${evidence.influence_evidence.influence_likely || false}\n`;
    evidenceText += `Direction aligned: ${evidence.influence_evidence.influence_direction_aligned || false}\n`;
    
    if (evidence.influence_evidence.other_supporting_insights?.length > 0) {
      evidenceText += `Supporting insights: ${evidence.influence_evidence.other_supporting_insights.join(", ")}\n`;
    }
    
    if (evidence.influence_evidence.other_conflicting_insights?.length > 0) {
      evidenceText += `Conflicting insights: ${evidence.influence_evidence.other_conflicting_insights.join(", ")}\n`;
    }
  }

  return evidenceText.trim() || "Evidence data structure not recognized.";
}

/**
 * Determine confidence level from evidence
 */
function determineConfidenceLevel(apiInsight: APIInsight): "high" | "medium" | "low" {
  if (!apiInsight.evidence || !apiInsight.evidence.active_evidence) {
    return "low";
  }

  const activeConfidence = apiInsight.evidence.active_evidence.active_confidence;
  
  if (typeof activeConfidence === "string") {
    switch (activeConfidence.toLowerCase()) {
      case "high":
        return "high";
      case "medium":
        return "medium";
      case "low":
        return "low";
      default:
        return "medium";
    }
  }

  // Default based on relationship type
  return apiInsight.relationship_type === "INFLUENCE_CONFIRMED" ? "medium" : "low";
}

/**
 * Categorize insight based on activity and metrics
 */
function categorizeInsight(apiInsight: APIInsight): string {
  const activity = apiInsight.activity_description.toLowerCase();
  const metric = apiInsight.metric_verbose_name.toLowerCase();
  
  // Basic categorization logic - can be enhanced
  if (activity.includes("promotion") || activity.includes("discount") || activity.includes("sale")) {
    return "promotional_impact";
  } else if (activity.includes("content") || activity.includes("blog") || activity.includes("article")) {
    return "content_marketing";
  } else if (activity.includes("email") || activity.includes("newsletter")) {
    return "email_marketing";
  } else if (activity.includes("social") || activity.includes("facebook") || activity.includes("twitter") || activity.includes("linkedin")) {
    return "social_media";
  } else if (activity.includes("campaign") || activity.includes("advertising") || activity.includes("ad")) {
    return "marketing_campaign";
  } else if (metric.includes("seasonal") || activity.includes("seasonal")) {
    return "seasonal_trend";
  } else {
    return "general_marketing";
  }
}

/**
 * Determine impact from relationship type and direction
 */
function determineImpact(apiInsight: APIInsight): "positive" | "negative" | "neutral" {
  if (apiInsight.relationship_type === "NO_INFLUENCE_CONFIRMED") {
    return "neutral";
  }
  
  if (apiInsight.direction === "positive") {
    return "positive";
  } else if (apiInsight.direction === "negative") {
    return "negative";
  } else {
    return "neutral";
  }
}

/**
 * Create date range (placeholder implementation)
 * In a real scenario, this would come from the activity log or metric data
 */
function createDateRange(): { start: string; end: string } {
  const endDate = new Date();
  const startDate = new Date();
  startDate.setDate(endDate.getDate() - 30); // Default to 30-day range
  
  return {
    start: startDate.toISOString().split('T')[0],
    end: endDate.toISOString().split('T')[0],
  };
}

/**
 * Transform array of API insights to frontend format
 */
export function transformAPIInsightsToFrontend(apiResponse: APIInsightResponse): FrontendInsight[] {
  return apiResponse.insights.map(transformAPIInsightToFrontend);
}