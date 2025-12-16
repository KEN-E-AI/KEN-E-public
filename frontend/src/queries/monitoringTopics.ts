import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AccountId } from "@/lib/branded-types";
import { monitoringTopicsService } from "@/services/monitoringTopicsService";
import type { CompetitorEntry, CustomerProfileEntry } from "@/types/monitoring";

export function useMonitoringTopics(accountId: AccountId | null) {
  return useQuery({
    queryKey: ["monitoring-topics", accountId],
    queryFn: () => {
      if (!accountId) throw new Error("Account ID is required");
      return monitoringTopicsService.getMonitoringTopics(accountId);
    },
    enabled: !!accountId,
  });
}

export function useAddCompetitorKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      data,
    }: {
      accountId: AccountId;
      data: CompetitorEntry;
    }) => {
      return monitoringTopicsService.addCompetitorKeywords(accountId, data);
    },
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}

export function useUpdateCompetitorKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      competitorIndex,
      data,
    }: {
      accountId: AccountId;
      competitorIndex: number;
      data: Partial<CompetitorEntry>;
    }) => {
      return monitoringTopicsService.updateCompetitorKeywords(
        accountId,
        competitorIndex,
        data,
      );
    },
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}

export function useDeleteCompetitorKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      competitorIndex,
    }: {
      accountId: AccountId;
      competitorIndex: number;
    }) => {
      return monitoringTopicsService.deleteCompetitorKeywords(
        accountId,
        competitorIndex,
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}

export function useAddCustomerProfileKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      data,
    }: {
      accountId: AccountId;
      data: CustomerProfileEntry;
    }) => {
      return monitoringTopicsService.addCustomerProfileKeywords(
        accountId,
        data,
      );
    },
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}

export function useUpdateCustomerProfileKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      customerProfileIndex,
      data,
    }: {
      accountId: AccountId;
      customerProfileIndex: number;
      data: Partial<CustomerProfileEntry>;
    }) => {
      return monitoringTopicsService.updateCustomerProfileKeywords(
        accountId,
        customerProfileIndex,
        data,
      );
    },
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}

export function useDeleteCustomerProfileKeywords() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      customerProfileIndex,
    }: {
      accountId: AccountId;
      customerProfileIndex: number;
    }) => {
      return monitoringTopicsService.deleteCustomerProfileKeywords(
        accountId,
        customerProfileIndex,
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", variables.accountId],
      });
    },
  });
}
