import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Product {
  node_id: string;
  account_id: string;
  product_name: string;
  description: string;
  references: string[];
  product_detail_page?: string;
  category_node_id: string;
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface ProductCreate {
  product_name: string;
  description: string;
  category_node_id: string;
  references?: string[];
  product_detail_page?: string;
}

export interface ProductUpdate {
  product_name?: string;
  description?: string;
  references?: string[];
  product_detail_page?: string;
}

interface ProductListResponse {
  products: Product[];
  total_count: number;
}

class ProductService {
  async list(
    accountId: AccountId,
    categoryNodeId?: string,
    substituteProductNodeId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<ProductListResponse> {
    const params: Record<string, any> = { skip, limit };
    if (categoryNodeId) params.category_node_id = categoryNodeId;
    if (substituteProductNodeId)
      params.substitute_product_node_id = substituteProductNodeId;

    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/products`,
      { params },
    );
    return response.data;
  }

  async create(accountId: AccountId, data: ProductCreate): Promise<Product> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/products`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: ProductUpdate,
  ): Promise<Product> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/products/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(`/api/v1/knowledge-graph/${accountId}/products/${nodeId}`);
  }
}

export const productService = new ProductService();
