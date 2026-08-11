import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { AppSettings } from "@/types/settings";

export function useSettings() {
  return useQuery({
    retry: false,
    queryKey: queryKeys.settings.all,
    queryFn: () => autotaskApi.settings.get(),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<AppSettings>) =>
      autotaskApi.settings.update(patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
    },
  });
}
