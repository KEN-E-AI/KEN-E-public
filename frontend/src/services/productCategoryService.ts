import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface ProductCategory {
  node_id: string;
  product_name: string;
  description: string;
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
}

export const productCategoryService = new ProductCategoryService();
