import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useRpaComponents() {
  return useQuery({
    queryKey: queryKeys.rpaComponents.all,
    queryFn: () => autotaskApi.rpaComponents.list(),
  });
}
