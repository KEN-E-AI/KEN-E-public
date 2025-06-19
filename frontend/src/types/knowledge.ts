// Product configuration types
export interface Product {
  id: string;
  name: string;
  description: string;
  connected: boolean;
  icon: string;
}

// Knowledge configuration section types
export interface ConfigurationSection {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<any>;
  type: "functional" | "placeholder";
  route?: string;
}

// Filter and sort types for configuration pages
export type SortDirection = "asc" | "desc";
export type SortField = string | null;
