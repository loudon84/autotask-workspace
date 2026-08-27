import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useOwnerCandidates(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.portalAccounts.ownerCandidates(),
    queryFn: () => autotaskApi.portalAccounts.listOwnerCandidates(),
    enabled,
    staleTime: 0,
    refetchOnMount: "always",
  });
}
