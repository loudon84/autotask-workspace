import { useMutation, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useUploadCategoryDocuments(category: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filePaths: string[]) =>
      autotaskApi.portalCategories.upload(category, filePaths),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.portalCategories.all,
      });
    },
  });
}

export function useDeleteCategoryDocument(category: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) =>
      autotaskApi.portalCategories.delete(category, documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.portalCategories.all,
      });
    },
  });
}
