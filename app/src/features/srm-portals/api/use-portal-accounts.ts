import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function usePortalAccounts() {
  return useQuery({
    queryKey: queryKeys.portalAccounts.list(),
    queryFn: () => autotaskApi.portalAccounts.list(),
  });
}

export function usePortalAccount(portalId: string) {
  return useQuery({
    queryKey: queryKeys.portalAccounts.detail(portalId),
    queryFn: () => autotaskApi.portalAccounts.get(portalId),
    enabled: Boolean(portalId),
  });
}
