import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useWorkers() {
  return useQuery({
    queryKey: queryKeys.workers.list(),
    queryFn: () => autotaskApi.workers.list(),
  });
}
