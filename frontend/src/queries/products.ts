import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productCategoryService } from "@/services/productCategoryService";
import { productService } from "@/services/productService";
import { valuePropositionService } from "@/services/valuePropositionService";
import type {
  ProductCategory,
  ProductCategoryCreate,
  ProductCategoryUpdate,
} from "@/services/productCategoryService";
import type {
  Product,
  ProductCreate,
  ProductUpdate,
} from "@/services/productService";
import type {
  ValueProposition,
  ValuePropositionCreate,
  ValuePropositionUpdate,
} from "@/services/valuePropositionService";
import type { AccountId } from "@/lib/branded-types";

// Query keys factory
export const productKeys = {
  all: ["products"] as const,
  categories: (accountId: AccountId) =>
    [...productKeys.all, "categories", accountId] as const,
  categoryList: (accountId: AccountId) =>
    [...productKeys.categories(accountId), "list"] as const,
  products: (accountId: AccountId, categoryId?: string) =>
    [...productKeys.all, "list", accountId, categoryId || "all"] as const,
  valuePropositions: (accountId: AccountId, parentNodeId?: string) =>
    [
      ...productKeys.all,
      "value-propositions",
      accountId,
      parentNodeId || "all",
    ] as const,
};

// Product categories query with caching
export const useProductCategories = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? productKeys.categoryList(accountId)
      : (["products", "categories", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { categories: [], total_count: 0 };
      return productCategoryService.list(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Products query with per-category caching
export const useProducts = (
  accountId: AccountId | null,
  categoryId: string | null,
) => {
  return useQuery({
    queryKey: accountId
      ? productKeys.products(accountId, categoryId || undefined)
      : (["products", "list", "none"] as const),
    queryFn: async () => {
      if (!accountId || !categoryId) return { products: [], total_count: 0 };
      return productService.list(accountId, categoryId);
    },
    enabled: !!accountId && !!categoryId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Product category mutations
export const useCreateProductCategory = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      category: ProductCategoryCreate;
    }) => productCategoryService.create(data.accountId, data.category),
    onSuccess: (_, variables) => {
      // Invalidate categories list
      queryClient.invalidateQueries({
        queryKey: productKeys.categoryList(variables.accountId),
      });
    },
  });
};

export const useUpdateProductCategory = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: ProductCategoryUpdate;
    }) =>
      productCategoryService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      // Invalidate categories list
      queryClient.invalidateQueries({
        queryKey: productKeys.categoryList(variables.accountId),
      });
    },
  });
};

export const useDeleteProductCategory = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; nodeId: string }) =>
      productCategoryService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      // Invalidate categories list
      queryClient.invalidateQueries({
        queryKey: productKeys.categoryList(variables.accountId),
      });
    },
  });
};

// Product mutations
export const useCreateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; product: ProductCreate }) =>
      productService.create(data.accountId, data.product),
    onSuccess: (newProduct, variables) => {
      // Invalidate products list for the specific category
      queryClient.invalidateQueries({
        queryKey: productKeys.products(
          variables.accountId,
          variables.product.category_node_id,
        ),
      });
    },
  });
};

export const useUpdateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: ProductUpdate;
      categoryId: string;
    }) => productService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      // Invalidate products list for the specific category
      queryClient.invalidateQueries({
        queryKey: productKeys.products(
          variables.accountId,
          variables.categoryId,
        ),
      });
    },
  });
};

export const useDeleteProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      categoryId: string;
    }) => productService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      // Invalidate products list for the specific category
      queryClient.invalidateQueries({
        queryKey: productKeys.products(
          variables.accountId,
          variables.categoryId,
        ),
      });
    },
  });
};

// Value Propositions query with per-parent caching
export const useValuePropositions = (
  accountId: AccountId | null,
  parentNodeId: string | null,
) => {
  return useQuery({
    queryKey: accountId
      ? productKeys.valuePropositions(accountId, parentNodeId || undefined)
      : (["products", "value-propositions", "none"] as const),
    queryFn: async () => {
      if (!accountId || !parentNodeId)
        return { value_propositions: [], total_count: 0 };
      return valuePropositionService.list(accountId, parentNodeId);
    },
    enabled: !!accountId && !!parentNodeId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Value Proposition mutations
export const useCreateValueProposition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      valueProposition: ValuePropositionCreate;
    }) => valuePropositionService.create(data.accountId, data.valueProposition),
    onSuccess: (_, variables) => {
      // Invalidate value propositions for the parent node
      queryClient.invalidateQueries({
        queryKey: productKeys.valuePropositions(
          variables.accountId,
          variables.valueProposition.parent_node_id,
        ),
      });
    },
  });
};

export const useUpdateValueProposition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: ValuePropositionUpdate;
      parentNodeId: string;
    }) =>
      valuePropositionService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      // Invalidate value propositions for the parent node
      queryClient.invalidateQueries({
        queryKey: productKeys.valuePropositions(
          variables.accountId,
          variables.parentNodeId,
        ),
      });
    },
  });
};

export const useDeleteValueProposition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      parentNodeId: string;
    }) => valuePropositionService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      // Invalidate value propositions for the parent node
      queryClient.invalidateQueries({
        queryKey: productKeys.valuePropositions(
          variables.accountId,
          variables.parentNodeId,
        ),
      });
    },
  });
};
