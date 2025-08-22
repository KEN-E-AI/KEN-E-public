import api from "@/lib/api";

export interface IndustryTemplate {
  id: string;
  industry: string;
  name: string;
  description: string;
  defaultObjectives: string[];
  defaultChannels: string[];
  defaultKPIs: string[];
  marketingChannels: string[];
  productIntegrations: string[];
  recommendedSettings: {
    timezone: string;
    data_region: string;
    industry: string;
  };
  defaultSettings: {
    data_retention: number;
  };
  created_at: string;
  updated_at: string;
}

// API response format (snake_case)
interface IndustryTemplateApiResponse {
  id: string;
  industry: string;
  name: string;
  description: string;
  default_objectives: string[];
  default_channels: string[];
  default_kpis: string[];
  marketing_channels: string[];
  product_integrations: string[];
  recommended_settings: {
    timezone: string;
    data_region: string;
    industry: string;
  };
  default_settings: {
    data_retention: number;
  };
  created_at: string;
  updated_at: string;
}

export interface IndustryTemplateListResponse {
  templates: IndustryTemplate[];
  total: number;
}

interface IndustryTemplateListApiResponse {
  templates: IndustryTemplateApiResponse[];
  total: number;
}

class TemplateService {
  // Transform API response from snake_case to camelCase
  private transformTemplate(
    apiTemplate: IndustryTemplateApiResponse,
  ): IndustryTemplate {
    return {
      id: apiTemplate.id,
      industry: apiTemplate.industry,
      name: apiTemplate.name,
      description: apiTemplate.description,
      defaultObjectives: apiTemplate.default_objectives || [],
      defaultChannels: apiTemplate.default_channels || [],
      defaultKPIs: apiTemplate.default_kpis || [],
      marketingChannels: apiTemplate.marketing_channels || [],
      productIntegrations: apiTemplate.product_integrations || [],
      recommendedSettings: apiTemplate.recommended_settings || {
        timezone: "America/New_York",
        data_region: "United States",
        industry: apiTemplate.industry,
      },
      defaultSettings: apiTemplate.default_settings || {
        data_retention: 90,
      },
      created_at: apiTemplate.created_at,
      updated_at: apiTemplate.updated_at,
    };
  }

  async getTemplateByIndustry(
    industry: string,
  ): Promise<IndustryTemplate | null> {
    try {
      const response = await api.get<IndustryTemplateApiResponse>(
        `/api/v1/industry-templates/industry/${encodeURIComponent(industry)}`,
      );
      return this.transformTemplate(response.data);
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.log(`No template found for industry ${industry}`);
        return null;
      }
      console.error(`Failed to get template for industry ${industry}:`, error);
      return null;
    }
  }

  async getAllTemplates(): Promise<IndustryTemplate[]> {
    try {
      const response = await api.get<IndustryTemplateListApiResponse>(
        "/api/v1/industry-templates",
      );
      return response.data.templates.map((template) =>
        this.transformTemplate(template),
      );
    } catch (error) {
      console.error("Failed to get all templates:", error);
      return [];
    }
  }

  async getTemplateById(templateId: string): Promise<IndustryTemplate | null> {
    try {
      const response = await api.get<IndustryTemplateApiResponse>(
        `/api/v1/industry-templates/${templateId}`,
      );
      return this.transformTemplate(response.data);
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.log(`Template ${templateId} not found`);
        return null;
      }
      console.error(`Failed to get template ${templateId}:`, error);
      return null;
    }
  }
}

export const templateService = new TemplateService();
