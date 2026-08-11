import { create } from "zustand";
import humanActionsData from "@/mock/human-actions.json";
import type { HumanAction } from "@/types/human-action";

interface HumanActionStore {
  overrides: Record<string, Partial<HumanAction>>;

  updateHumanAction: (id: string, patch: Partial<HumanAction>) => void;
}

export const useHumanActionStore = create<HumanActionStore>((set) => ({
  overrides: {},

  updateHumanAction: (id, patch) =>
    set((state) => ({
      overrides: {
        ...state.overrides,
        [id]: {
          ...state.overrides[id],
          ...patch,
        },
      },
    })),
}));

export function mergeHumanActions(
  baseActions: HumanAction[],
  overrides: Record<string, Partial<HumanAction>>
): HumanAction[] {
  return baseActions.map((action) => ({
    ...action,
    ...overrides[action.id],
  }));
}

export function getHumanActionsFromStore(): HumanAction[] {
  const state = useHumanActionStore.getState();
  return mergeHumanActions(humanActionsData as HumanAction[], state.overrides);
}

export function getHumanActionByTaskId(taskId: string): HumanAction | undefined {
  return getHumanActionsFromStore().find((a) => a.taskId === taskId);
}

export function getHumanActionById(id: string): HumanAction | undefined {
  return getHumanActionsFromStore().find((a) => a.id === id);
}
