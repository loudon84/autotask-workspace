import { useMutation, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { CreateAutomationTaskInput } from "@/types/automation-task";

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (task: CreateAutomationTaskInput) =>
      autotaskApi.tasks.create(task),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useStartTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => autotaskApi.tasks.start(taskId),
    onSuccess: (_data, taskId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => autotaskApi.tasks.cancel(taskId),
    onSuccess: (_data, taskId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useRetryTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => autotaskApi.tasks.retry(taskId),
    onSuccess: (_data, taskId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}

export function useUpdateTaskStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      status,
      extra,
    }: {
      taskId: string;
      status: import("@/types/automation-task").AutomationTaskStatus;
      extra?: Record<string, unknown>;
    }) =>
      autotaskApi.tasks.updateStatus(taskId, status).then((task) => {
        if (extra) {
          return autotaskApi.tasks.update(taskId, extra);
        }
        return task;
      }),
    onSuccess: (_data, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useMarkHumanOpened() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      taskId: string;
      humanActionId: string;
      openedBy?: string;
      clientTabId?: string;
    }) => autotaskApi.tasks.markHumanOpened(input),
    onSuccess: (_data, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.humanAction(taskId),
      });
    },
  });
}

export function useConfirmHumanAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      taskId: string;
      humanActionId: string;
      confirmedBy?: string;
      note?: string;
    }) => autotaskApi.tasks.confirmHumanAction(input),
    onSuccess: (_data, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.detail(taskId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.tasks.humanAction(taskId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}
