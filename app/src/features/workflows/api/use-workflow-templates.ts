import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiClientError } from "@/actions/autotask-api";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type {
  CreateWorkflowTemplateInput,
  UpdateWorkflowTemplateInput,
} from "@/types/workflow";

export function useWorkflowTemplates() {
  return useQuery({
    queryKey: queryKeys.workflows.list(),
    queryFn: () => autotaskApi.workflowTemplates.list(),
  });
}

export function useWorkflowTemplate(workflowId: string) {
  return useQuery({
    queryKey: queryKeys.workflows.detail(workflowId),
    queryFn: () => autotaskApi.workflowTemplates.get(workflowId),
    enabled: Boolean(workflowId),
  });
}

export function useCreateWorkflowTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWorkflowTemplateInput) =>
      autotaskApi.workflowTemplates.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
    },
  });
}

export function useUpdateWorkflowTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      workflowId,
      input,
    }: {
      workflowId: string;
      input: UpdateWorkflowTemplateInput;
    }) => autotaskApi.workflowTemplates.update(workflowId, input),
    onSuccess: (_data, { workflowId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflows.detail(workflowId),
      });
    },
  });
}

export function useSetWorkflowTemplateStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      workflowId,
      status,
    }: {
      workflowId: string;
      status: "enabled" | "disabled";
    }) => autotaskApi.workflowTemplates.setStatus(workflowId, status),
    onSuccess: (_data, { workflowId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflows.detail(workflowId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflowBindings.all,
      });
    },
  });
}

interface WorkflowDeleteErrorBody {
  message?: string;
  message_key?: string;
}

export function getWorkflowDeleteErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 409) {
    const body = error.body as WorkflowDeleteErrorBody | undefined;
    if (
      body?.message_key === "errors.autotask.workflow_delete_binding_referenced"
    ) {
      return "模板已被 Binding 引用，只能禁用";
    }
    if (
      body?.message_key === "errors.autotask.workflow_delete_task_referenced"
    ) {
      return "模板已被历史任务引用，只能禁用";
    }
    if (
      body?.message_key === "errors.autotask.workflow_delete_requires_disabled"
    ) {
      return "启用中的模板不能删除，请先禁用";
    }
    return body?.message || error.message || "模板当前不能删除";
  }
  return error instanceof Error ? error.message : "删除模板失败";
}

export function useDeleteWorkflowTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workflowId: string) =>
      autotaskApi.workflowTemplates.delete(workflowId),
    onSuccess: (_data, workflowId) => {
      queryClient.removeQueries({
        queryKey: queryKeys.workflows.detail(workflowId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.workflowBindings.all,
      });
      toast.success("模板已删除");
    },
    onError: (error) => {
      toast.error(getWorkflowDeleteErrorMessage(error));
    },
  });
}
