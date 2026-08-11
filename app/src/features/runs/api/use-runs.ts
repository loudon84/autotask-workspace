import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import {
  getRemoteRefreshInterval,
  LIVE_LOG_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useRuns() {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.runs.list(),
    queryFn: () => autotaskApi.runs.list(),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useRun(runId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.runs.detail(runId),
    queryFn: () => autotaskApi.runs.get(runId),
    enabled: Boolean(runId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_LOG_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}

export function useRunsByTask(taskId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.runs.byTask(taskId),
    queryFn: () => autotaskApi.runs.listByTask(taskId),
    enabled: Boolean(taskId),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useRunEvents(runId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.runs.events(runId),
    queryFn: () => autotaskApi.runs.listEvents(runId),
    enabled: Boolean(runId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_LOG_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}
