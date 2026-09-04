import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import {
  getRemoteRefreshInterval,
  LIVE_STATUS_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useBoePackingList(params?: { stage?: string; keyword?: string }) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.boePacking.list(params),
    queryFn: () => autotaskApi.boePacking.list(params),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useBoePackingDetail(instanceId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.boePacking.detail(instanceId),
    queryFn: () => autotaskApi.boePacking.get(instanceId),
    enabled: Boolean(instanceId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_STATUS_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}
