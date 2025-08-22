import api from "@/lib/api";

export interface IndustryTemplate {
  id: string;
  industry: string;
  name: string;
  description: string;
  definition: string;
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

export interface IndustryTemplateListResponse {
  templates: IndustryTemplate[];
  total: number;
}

class TemplateService {
  async getTemplateByIndustry(
    industry: string,
  ): Promise<IndustryTemplate | null> {
    try {
      const response = await api.get<IndustryTemplate>(
        `/api/v1/industry-templates/industry/${encodeURIComponent(industry)}`,
      );
      return response.data;
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
      const response = await api.get<IndustryTemplateListResponse>(
        "/api/v1/industry-templates",
      );
      return response.data.templates;
    } catch (error) {
      console.error("Failed to get all templates:", error);
      return [];
    }
  }

  async getTemplateById(templateId: string): Promise<IndustryTemplate | null> {
    try {
      const response = await api.get<IndustryTemplate>(
        `/api/v1/industry-templates/${templateId}`,
      );
      return response.data;
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
