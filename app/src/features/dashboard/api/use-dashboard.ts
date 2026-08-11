import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import { getRemoteRefreshInterval } from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useDashboard() {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.dashboard.summary(),
    queryFn: () => autotaskApi.dashboard.getSummary(),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}
