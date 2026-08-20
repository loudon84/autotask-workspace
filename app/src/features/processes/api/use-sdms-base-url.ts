import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useSdmsBaseUrl(): string {
  const { data } = useQuery({
    queryKey: queryKeys.integrationEndpoints.all,
    queryFn: () => autotaskApi.integrationEndpoints.get(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  return (data?.sdmsBaseUrl ?? "").trim();
}
