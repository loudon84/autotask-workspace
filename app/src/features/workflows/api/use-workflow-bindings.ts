import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type {
  CreateWorkflowBindingInput,
  UpdateWorkflowBindingInput,
  WorkflowBindingStatus,
} from "@/types/workflow-binding";

export function useWorkflowBindings() {
  return useQuery({
    queryKey: queryKeys.workflowBindings.list(),
    queryFn: () => autotaskApi.workflowBindings.list(),
  });
}

export function useCreateWorkflowBinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWorkflowBindingInput) =>
      autotaskApi.workflowBindings.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflowBindings.all,
      });
    },
  });
}

export function useUpdateWorkflowBinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      bindingId,
      input,
    }: {
      bindingId: string;
      input: UpdateWorkflowBindingInput;
    }) => autotaskApi.workflowBindings.update(bindingId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflowBindings.all,
      });
    },
  });
}

export function useSetWorkflowBindingStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      bindingId,
      status,
    }: {
      bindingId: string;
      status: WorkflowBindingStatus;
    }) => autotaskApi.workflowBindings.setStatus(bindingId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflowBindings.all,
      });
    },
  });
}
