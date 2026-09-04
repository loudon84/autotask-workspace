import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { Timer } from "@/features/schedulers/types";

export function useSchedulerJobs(enabled?: boolean) {
  return useQuery({
    queryKey: queryKeys.schedulerJobs.list(enabled),
    queryFn: () => autotaskApi.timers.list(enabled),
  });
}

export function useSchedulerJob(jobId: string) {
  return useQuery({
    queryKey: queryKeys.schedulerJobs.detail(jobId),
    queryFn: () => autotaskApi.timers.get(jobId),
    enabled: Boolean(jobId),
  });
}

export function useSchedulerJobRuns(jobId: string, page = 1) {
  return useQuery({
    queryKey: [...queryKeys.schedulerJobs.runs(jobId), page],
    queryFn: () => autotaskApi.timers.listRuns(jobId, page),
    enabled: Boolean(jobId),
  });
}

export function useUpdateSchedulerJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: { name?: string; enabled?: boolean; cron?: string }) =>
      autotaskApi.timers.patch(jobId, patch),
    onSuccess: (data: Timer) => {
      queryClient.setQueryData(queryKeys.schedulerJobs.detail(jobId), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.schedulerJobs.all });
    },
  });
}

export function useRunSchedulerJobNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => autotaskApi.timers.runNow(jobId),
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.schedulerJobs.runs(jobId),
      });
    },
  });
}
