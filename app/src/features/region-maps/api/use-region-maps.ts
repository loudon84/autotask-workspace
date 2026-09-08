import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useRegionMaps() {
  return useQuery({
    queryKey: queryKeys.regionMaps.list(),
    queryFn: () => autotaskApi.regionMaps.list(),
  });
}

export function useUpsertRegionMap() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      regionCode: string;
      defaultName: string;
      boeName?: string;
    }) => autotaskApi.regionMaps.upsert(body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.regionMaps.all,
      });
    },
  });
}

export function useDeleteRegionMap() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mapId: string) => autotaskApi.regionMaps.delete(mapId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.regionMaps.all,
      });
    },
  });
}
