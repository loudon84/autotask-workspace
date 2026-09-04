import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/services/api-client";
import { mapItemResponse } from "@/services/dto-mappers";
import { queryKeys } from "@/services/query-keys";
import type { SchedulerSettings } from "@/types/settings";

const DEFAULT_BOE_PACK_CRON = "0 7 * * *";

// mapItemResponse 已将响应键转为 camelCase（sign_poll → signPoll）
interface SchedulerSettingsDTO {
  signPoll: { enabled: boolean; cron: string };
  scan: { enabled: boolean; cron: string };
  boePack?: { enabled: boolean; cron: string };
  nextRunAt?: {
    signPoll?: string | null;
    scan?: string | null;
    boePack?: string | null;
  };
}

function fromDTO(dto: SchedulerSettingsDTO): SchedulerSettings {
  return {
    signPoll: { enabled: dto.signPoll.enabled, cron: dto.signPoll.cron },
    scan: { enabled: dto.scan.enabled, cron: dto.scan.cron },
    boePack: {
      enabled: dto.boePack?.enabled ?? false,
      cron: dto.boePack?.cron ?? DEFAULT_BOE_PACK_CRON,
    },
    nextRunAt: {
      signPoll: dto.nextRunAt?.signPoll ?? null,
      scan: dto.nextRunAt?.scan ?? null,
      boePack: dto.nextRunAt?.boePack ?? null,
    },
  };
}

export type SchedulerSettingsPatch = {
  signPoll?: { enabled: boolean; cron: string };
  scan?: { enabled: boolean; cron: string };
  boePack?: { enabled: boolean; cron: string };
};

async function getSchedulerSettings(): Promise<SchedulerSettings> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: "/settings/schedulers",
  });
  return fromDTO(mapItemResponse<SchedulerSettingsDTO>(data));
}

async function updateSchedulerSettings(
  payload: SchedulerSettingsPatch
): Promise<SchedulerSettings> {
  const body: Record<string, { enabled: boolean; cron: string }> = {};
  if (payload.signPoll) {
    body.sign_poll = {
      enabled: payload.signPoll.enabled,
      cron: payload.signPoll.cron,
    };
  }
  if (payload.scan) {
    body.scan = {
      enabled: payload.scan.enabled,
      cron: payload.scan.cron,
    };
  }
  if (payload.boePack) {
    body.boe_pack = {
      enabled: payload.boePack.enabled,
      cron: payload.boePack.cron,
    };
  }
  const data = await apiRequest<unknown>({
    method: "PUT",
    path: "/settings/schedulers",
    body,
  });
  return fromDTO(mapItemResponse<SchedulerSettingsDTO>(data));
}

export function useSchedulerSettings() {
  return useQuery({
    retry: false,
    queryKey: queryKeys.settings.schedulers,
    queryFn: getSchedulerSettings,
  });
}

export function useUpdateSchedulerSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSchedulerSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settings.schedulers, data);
    },
  });
}
