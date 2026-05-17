import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listSuperAdmins,
  grantSuperAdmin,
  revokeSuperAdmin,
} from "@/data/superAdminsApi";
import type { GrantSuperAdminRequest } from "@/data/superAdminsApi";

export const superAdminKeys = {
  all: ["superAdmins"] as const,
  list: () => [...superAdminKeys.all, "list"] as const,
};

export function useSuperAdmins() {
  return useQuery({
    queryKey: superAdminKeys.list(),
    queryFn: listSuperAdmins,
    staleTime: 1000 * 30,
  });
}

export function useGrantSuperAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: GrantSuperAdminRequest) => grantSuperAdmin(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: superAdminKeys.list() });
    },
  });
}

export function useRevokeSuperAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (uid: string) => revokeSuperAdmin(uid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: superAdminKeys.list() });
    },
  });
}
