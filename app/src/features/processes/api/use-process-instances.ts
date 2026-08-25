import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import {
  getRemoteRefreshInterval,
  LIVE_STATUS_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useProcessInstances(params?: {
  stage?: string;
  status?: string;
  keyword?: string;
}) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.processInstances.list(params),
    queryFn: () => autotaskApi.processInstances.list(params),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useProcessInstance(instanceId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.processInstances.detail(instanceId),
    queryFn: () => autotaskApi.processInstances.get(instanceId),
    enabled: Boolean(instanceId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_STATUS_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}
