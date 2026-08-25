import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { SchedulerJob } from "@/features/schedulers/types";

export function useSchedulerJobs(enabled?: boolean) {
  return useQuery({
    queryKey: queryKeys.schedulerJobs.list(enabled),
    queryFn: () => autotaskApi.schedulerJobs.list(enabled),
  });
}

export function useSchedulerJob(jobId: string) {
  return useQuery({
    queryKey: queryKeys.schedulerJobs.detail(jobId),
    queryFn: () => autotaskApi.schedulerJobs.get(jobId),
    enabled: Boolean(jobId),
  });
}

export function useSchedulerJobTasks(jobId: string) {
  return useQuery({
    queryKey: queryKeys.schedulerJobs.tasks(jobId),
    queryFn: () => autotaskApi.schedulerJobs.listTasks(jobId),
    enabled: Boolean(jobId),
  });
}

export function useUpdateSchedulerJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: { enabled?: boolean; cron?: string }) =>
      autotaskApi.schedulerJobs.patch(jobId, patch),
    onSuccess: (data: SchedulerJob) => {
      queryClient.setQueryData(queryKeys.schedulerJobs.detail(jobId), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.schedulerJobs.all });
    },
  });
}
