import { z } from "zod";

// Validation schema for account profile
export const accountProfileSchema = z.object({
  account_name: z
    .string()
    .min(1, "Account name is required")
    .max(100, "Account name must be less than 100 characters")
    .regex(
      /^[a-zA-Z0-9\s\-_]+$/,
      "Account name can only contain letters, numbers, spaces, hyphens, and underscores",
    ),

  industry: z.string().min(1, "Industry is required"),

  status: z.enum(["Active", "Inactive", "Setup", "Paused"]).default("Active"),

  timezone: z.string().optional(),

  website: z
    .union([z.string().url("Invalid website URL"), z.literal("")])
    .optional(),

  location: z
    .string()
    .max(100, "Location must be less than 100 characters")
    .optional(),

  template_id: z.string().optional(),
});

// Validation schema for marketing objectives
export const marketingObjectiveSchema = z.object({
  id: z.string(),
  name: z
    .string()
    .min(1, "Objective name is required")
    .max(100, "Objective name must be less than 100 characters"),

  description: z
    .string()
    .max(500, "Description must be less than 500 characters")
    .optional(),

  priority: z.enum(["high", "medium", "low"]).default("medium"),

  status: z.enum(["active", "paused", "completed"]).default("active"),
});

// Validation schema for marketing channels
export const marketingChannelSchema = z.object({
  id: z.string(),
  name: z
    .string()
    .min(1, "Channel name is required")
    .max(100, "Channel name must be less than 100 characters"),

  budget: z
    .number()
    .min(0, "Budget must be non-negative")
    .max(10000000, "Budget must be less than $10,000,000"),

  status: z.enum(["active", "paused"]).default("active"),

  tactics: z.array(z.string()).default([]),
});

// Validation schema for marketing settings
export const marketingSettingsSchema = z.object({
  objectives: z
    .array(marketingObjectiveSchema)
    .min(1, "At least one objective is required"),

  channels: z
    .array(marketingChannelSchema)
    .min(1, "At least one channel is required"),

  budget: z.object({
    total: z
      .number()
      .min(0, "Total budget must be non-negative")
      .max(100000000, "Total budget must be less than $100,000,000"),

    period: z.enum(["monthly", "quarterly", "yearly"]).default("monthly"),
  }),

  settings: z.object({
    auto_optimization: z.boolean().default(true),
    performance_alerts: z.boolean().default(true),
    budget_alerts: z.boolean().default(true),
  }),
});

// File validation helper
const fileSchema = z
  .instanceof(File)
  .refine(
    (file) => {
      const allowedTypes = [
        ".pdf",
        ".xlsx",
        ".docx",
        ".pptx",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
      ];
      const fileExt = "." + file.name.split(".").pop()?.toLowerCase();
      return allowedTypes.includes(fileExt);
    },
    { message: "File type not supported" },
  )
  .refine(
    (file) => file.size <= 25 * 1024 * 1024, // 25MB
    { message: "File size must be less than 25MB" },
  );

// Validation schema for account creation
export const accountCreationSchema = z.object({
  account_name: z
    .string()
    .min(1, "Account name is required")
    .max(100, "Account name must be less than 100 characters"),

  description: z
    .string()
    .max(500, "Description must be less than 500 characters")
    .optional(),

  industry: z.string().min(1, "Industry is required"),

  websites: z
    .array(z.union([z.string().url("Invalid website URL"), z.literal("")]))
    .min(1, "At least one website is required")
    .default([""]),

  estimated_annual_ad_budget: z
    .number()
    .min(0, "Budget must be non-negative")
    .max(1000000000, "Budget must be less than $1,000,000,000")
    .nullable()
    .optional(),

  business_strategy_documents: z
    .array(fileSchema)
    .max(10, "Maximum 10 files allowed")
    .refine(
      (files) => {
        const totalSize = files.reduce((sum, file) => sum + file.size, 0);
        return totalSize <= 100 * 1024 * 1024; // 100MB
      },
      { message: "Total file size must be less than 100MB" },
    )
    .default([]),

  template_id: z.string().min(1, "Template selection is required"),

  marketing_channels: z
    .array(z.string())
    .min(1, "At least one marketing channel is required"),

  product_integrations: z.array(z.string()).default([]), // Optional

  enabled_strategies: z
    .array(z.string())
    .min(1, "At least one strategy must be selected")
    .default(["business_strategy", "competitive_strategy", "marketing_strategy", "brand_guidelines"]),

  override_product_categories: z.array(z.string()).default([]),

  objectives: z.array(z.string()).min(1, "At least one objective is required"),

  kpis: z.array(z.string()).min(1, "At least one KPI is required"),

  timezone: z.string().min(1, "Timezone is required"),

  data_region: z.string().min(1, "Data region is required"),

  region: z
    .array(z.string())
    .min(1, "At least one customer region is required"),
});

// Validation schema for KPI
export const kpiSchema = z.object({
  id: z.string(),
  name: z
    .string()
    .min(1, "KPI name is required")
    .max(100, "KPI name must be less than 100 characters"),

  description: z
    .string()
    .max(500, "Description must be less than 500 characters")
    .optional(),

  target: z.number().min(0, "Target must be non-negative"),

  current: z.number().min(0, "Current value must be non-negative"),

  unit: z.string().max(20, "Unit must be less than 20 characters").optional(),

  trend: z.enum(["up", "down", "stable"]).default("stable"),

  frequency: z.enum(["daily", "weekly", "monthly"]).default("monthly"),

  alerts: z.object({
    threshold: z.number().min(0, "Threshold must be non-negative"),
    type: z.enum(["above", "below"]).default("below"),
    enabled: z.boolean().default(false),
  }),
});

// Type exports
export type AccountProfileData = z.infer<typeof accountProfileSchema>;
export type MarketingObjectiveData = z.infer<typeof marketingObjectiveSchema>;
export type MarketingChannelData = z.infer<typeof marketingChannelSchema>;
export type MarketingSettingsData = z.infer<typeof marketingSettingsSchema>;
export type AccountCreationData = z.infer<typeof accountCreationSchema>;
export type KPIData = z.infer<typeof kpiSchema>;

// Validation helper functions
export const validateAccountProfile = (data: unknown) => {
  try {
    return {
      success: true,
      data: accountProfileSchema.parse(data),
      errors: null,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        success: false,
        data: null,
        errors: error.errors.map((err) => ({
          field: err.path.join("."),
          message: err.message,
        })),
      };
    }
    return {
      success: false,
      data: null,
      errors: [{ field: "unknown", message: "Validation failed" }],
    };
  }
};

export const validateMarketingSettings = (data: unknown) => {
  try {
    return {
      success: true,
      data: marketingSettingsSchema.parse(data),
      errors: null,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        success: false,
        data: null,
        errors: error.errors.map((err) => ({
          field: err.path.join("."),
          message: err.message,
        })),
      };
    }
    return {
      success: false,
      data: null,
      errors: [{ field: "unknown", message: "Validation failed" }],
    };
  }
};

export const validateAccountCreation = (data: unknown) => {
  try {
    return {
      success: true,
      data: accountCreationSchema.parse(data),
      errors: null,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        success: false,
        data: null,
        errors: error.errors.map((err) => ({
          field: err.path.join("."),
          message: err.message,
        })),
      };
    }
    return {
      success: false,
      data: null,
      errors: [{ field: "unknown", message: "Validation failed" }],
    };
  }
};
