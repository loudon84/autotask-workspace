import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiClientError } from "@/actions/autotask-api";
import { usePortalWritePermission } from "@/features/srm-portals/hooks/use-portal-write-permission";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type {
  CreatePortalAccountInput,
  UpdatePortalAccountInput,
} from "@/types/portal-account";

export function useCreatePortalAccount() {
  const queryClient = useQueryClient();
  const markForbidden = usePortalWritePermission((s) => s.markForbidden);

  return useMutation({
    mutationFn: (input: CreatePortalAccountInput) =>
      autotaskApi.portalAccounts.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portalAccounts.all });
      toast.success("创建成功");
    },
    onError: (err) => {
      if (err instanceof ApiClientError && err.status === 403) {
        markForbidden();
        return;
      }
      if (!(err instanceof ApiClientError && err.status === 422)) {
        toast.error(err instanceof Error ? err.message : "创建失败");
      }
    },
  });
}

export function useUpdatePortalAccount() {
  const queryClient = useQueryClient();
  const markForbidden = usePortalWritePermission((s) => s.markForbidden);

  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: string;
      patch: UpdatePortalAccountInput;
    }) => autotaskApi.portalAccounts.update(id, patch),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portalAccounts.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.portalAccounts.detail(id),
      });
      toast.success("保存成功");
    },
    onError: (err) => {
      if (err instanceof ApiClientError && err.status === 403) {
        markForbidden();
        return;
      }
      if (!(err instanceof ApiClientError && err.status === 422)) {
        toast.error(err instanceof Error ? err.message : "保存失败");
      }
    },
  });
}

export function useDeletePortalAccount() {
  const queryClient = useQueryClient();
  const markForbidden = usePortalWritePermission((s) => s.markForbidden);

  return useMutation({
    mutationFn: (id: string) => autotaskApi.portalAccounts.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portalAccounts.all });
      toast.success("删除成功");
    },
    onError: (err) => {
      if (err instanceof ApiClientError && err.status === 403) {
        markForbidden();
        return;
      }
      toast.error(err instanceof Error ? err.message : "删除失败");
    },
  });
}

export function useDisablePortalAccount() {
  const queryClient = useQueryClient();
  const markForbidden = usePortalWritePermission((s) => s.markForbidden);

  return useMutation({
    mutationFn: (id: string) =>
      autotaskApi.portalAccounts.update(id, { status: "DISABLED" }),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portalAccounts.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.portalAccounts.detail(id),
      });
      toast.success("已禁用");
    },
    onError: (err) => {
      if (err instanceof ApiClientError && err.status === 403) {
        markForbidden();
        return;
      }
      toast.error(err instanceof Error ? err.message : "禁用失败");
    },
  });
}
