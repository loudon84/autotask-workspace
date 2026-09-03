import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function usePortalCategories() {
  return useQuery({
    queryKey: queryKeys.portalCategories.list(),
    queryFn: () => autotaskApi.portalCategories.list(),
  });
}

export function useCategoryDocuments(category: string) {
  return useQuery({
    queryKey: queryKeys.portalCategories.documents(category),
    queryFn: () => autotaskApi.portalCategories.listDocuments(category),
    enabled: Boolean(category),
  });
}
