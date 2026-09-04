import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

export function useRegionMaps(category: string) {
  return useQuery({
    queryKey: queryKeys.regionMaps.list(category),
    queryFn: () => autotaskApi.regionMaps.list(category),
    enabled: Boolean(category),
  });
}

export function useUpsertRegionMap(category: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { regionCode: string; srmDisplayName: string }) =>
      autotaskApi.regionMaps.upsert({
        category,
        regionCode: body.regionCode,
        srmDisplayName: body.srmDisplayName,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.regionMaps.list(category),
      });
    },
  });
}

export function useDeleteRegionMap(category: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mapId: string) => autotaskApi.regionMaps.delete(mapId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.regionMaps.list(category),
      });
    },
  });
}
