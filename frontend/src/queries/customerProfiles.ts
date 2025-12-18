import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { customerProfileService } from "@/services/customerProfileService";
import { productCategoryService } from "@/services/productCategoryService";
import type {
  CustomerProfile,
  CustomerProfileCreate,
  CustomerProfileUpdate,
} from "@/services/customerProfileService";
import type { AccountId } from "@/lib/branded-types";

// Query keys factory
export const customerProfileKeys = {
  all: ["customer-profiles"] as const,
  list: (accountId: AccountId) =>
    [...customerProfileKeys.all, "list", accountId] as const,
  linkedCategories: (accountId: AccountId, customerProfileId: string) =>
    [
      ...customerProfileKeys.all,
      "linked-categories",
      accountId,
      customerProfileId,
    ] as const,
};

// Customer profiles query with caching
export const useCustomerProfiles = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? customerProfileKeys.list(accountId)
      : (["customer-profiles", "list", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { customer_profiles: [], total_count: 0 };
      return customerProfileService.list(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Customer profile mutations
export const useCreateCustomerProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      profile: CustomerProfileCreate;
    }) => customerProfileService.create(data.accountId, data.profile),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: customerProfileKeys.list(variables.accountId),
      });
    },
  });
};

export const useUpdateCustomerProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: CustomerProfileUpdate;
    }) =>
      customerProfileService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: customerProfileKeys.list(variables.accountId),
      });
    },
  });
};

export const useDeleteCustomerProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; nodeId: string }) =>
      customerProfileService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: customerProfileKeys.list(variables.accountId),
      });
    },
  });
};

// Linked product categories query
export const useLinkedProductCategories = (
  accountId: AccountId | null,
  customerProfileId: string | null,
) => {
  return useQuery({
    queryKey:
      accountId && customerProfileId
        ? customerProfileKeys.linkedCategories(accountId, customerProfileId)
        : (["customer-profiles", "linked-categories", "none"] as const),
    queryFn: async () => {
      if (!accountId || !customerProfileId)
        return { categories: [], total_count: 0 };
      return productCategoryService.listLinkedToCustomerProfile(
        accountId,
        customerProfileId,
      );
    },
    enabled: !!accountId && !!customerProfileId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Link/unlink mutations
export const useLinkProductCategoryToProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      productCategoryId: string;
      customerProfileId: string;
    }) =>
      productCategoryService.linkToCustomerProfile(
        data.accountId,
        data.productCategoryId,
        data.customerProfileId,
      ),
    onSuccess: (_, variables) => {
      // Invalidate linked categories for this profile (Customers page)
      queryClient.invalidateQueries({
        queryKey: customerProfileKeys.linkedCategories(
          variables.accountId,
          variables.customerProfileId,
        ),
      });
      // Invalidate linked profiles for this category (Strategy page)
      queryClient.invalidateQueries({
        queryKey: [
          "products",
          "linked-customer-profiles",
          variables.accountId,
          variables.productCategoryId,
        ],
      });
    },
  });
};

export const useUnlinkProductCategoryFromProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      productCategoryId: string;
      customerProfileId: string;
    }) =>
      productCategoryService.unlinkFromCustomerProfile(
        data.accountId,
        data.productCategoryId,
        data.customerProfileId,
      ),
    onSuccess: (_, variables) => {
      // Invalidate linked categories for this profile
      queryClient.invalidateQueries({
        queryKey: customerProfileKeys.linkedCategories(
          variables.accountId,
          variables.customerProfileId,
        ),
      });
    },
  });
};
