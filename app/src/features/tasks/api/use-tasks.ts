import { useQuery } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import {
  getRemoteRefreshInterval,
  LIVE_STATUS_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";
import { queryKeys } from "@/services/query-keys";

export function useTasks() {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.tasks.list(),
    queryFn: () => autotaskApi.tasks.list(),
    refetchInterval: getRemoteRefreshInterval(isRemote),
    refetchIntervalInBackground: isRemote,
  });
}

export function useTask(taskId: string) {
  const isRemote = getApiMode() === "remote";
  return useQuery({
    queryKey: queryKeys.tasks.detail(taskId),
    queryFn: () => autotaskApi.tasks.get(taskId),
    enabled: Boolean(taskId),
    refetchInterval: getRemoteRefreshInterval(
      isRemote,
      LIVE_STATUS_REFRESH_INTERVAL_MS
    ),
    refetchIntervalInBackground: isRemote,
  });
}

export function useAuditLogs(taskId: string) {
  return useQuery({
    queryKey: queryKeys.tasks.auditLogs(taskId),
    queryFn: () => autotaskApi.auditLogs.list(taskId),
    enabled: Boolean(taskId),
  });
}

export function useHumanAction(taskId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tasks.humanAction(taskId),
    queryFn: () => autotaskApi.tasks.getHumanAction(taskId),
    enabled: Boolean(taskId) && enabled,
  });
}

export function useIntegrationCalls(taskId: string) {
  return useQuery({
    queryKey: queryKeys.tasks.integrationCalls(taskId),
    queryFn: () => autotaskApi.tasks.integrationCalls(taskId),
    enabled: Boolean(taskId),
  });
}
