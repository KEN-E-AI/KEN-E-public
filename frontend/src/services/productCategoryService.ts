import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface ProductCategory {
  node_id: string;
  product_name: string;
  description: string;
  strategy_count?: number; // Count of strategies for this category (when linked to customer profile)
  account_id?: string;
  created_at?: string;
  updated_at?: string;
  created_time?: string;
  last_modified?: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface ProductCategoryCreate {
  product_name: string;
  description: string;
}

export interface ProductCategoryUpdate {
  product_name?: string;
  description?: string;
}

interface ProductCategoryListResponse {
  categories: ProductCategory[];
  total_count: number;
}

class ProductCategoryService {
  async list(
    accountId: AccountId,
    skip = 0,
    limit = 1000,
  ): Promise<ProductCategoryListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/product-categories`,
      { params: { skip, limit } },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: ProductCategoryCreate,
  ): Promise<ProductCategory> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/product-categories`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: ProductCategoryUpdate,
  ): Promise<ProductCategory> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/product-categories/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/product-categories/${nodeId}`,
    );
  }

  async listLinkedToCustomerProfile(
    accountId: AccountId,
    customerProfileId: string,
  ): Promise<ProductCategoryListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles/${customerProfileId}/product-categories`,
    );
    return response.data;
  }

  async linkToCustomerProfile(
    accountId: AccountId,
    productCategoryId: string,
    customerProfileNodeId: string,
  ): Promise<void> {
    await api.post(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles/${customerProfileNodeId}/link-product-category`,
      { product_category_node_id: productCategoryId },
    );
  }

  async unlinkFromCustomerProfile(
    accountId: AccountId,
    productCategoryId: string,
    customerProfileNodeId: string,
  ): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles/${customerProfileNodeId}/unlink-product-category/${productCategoryId}`,
    );
  }

  async listLinkedCustomerProfiles(
    accountId: AccountId,
    productCategoryId: string,
  ): Promise<{ customer_profiles: any[]; total_count: number }> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/product-categories/${productCategoryId}/customer-profiles`,
    );
    return response.data;
  }
}

export const productCategoryService = new ProductCategoryService();
