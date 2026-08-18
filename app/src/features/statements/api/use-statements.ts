import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import {
  getRemoteRefreshInterval,
  LIVE_STATUS_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useStatements(params?: { checkStatus?: string; stage?: string }) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.statements.list(params),
    queryFn: () => autotaskApi.statements.list(params),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useStatement(billId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.statements.detail(billId),
    queryFn: () => autotaskApi.statements.get(billId),
    enabled: Boolean(billId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_STATUS_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}
