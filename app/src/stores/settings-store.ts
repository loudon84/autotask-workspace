import { create } from "zustand";
import type { AppSettings } from "@/types/settings";
import defaultSettings from "@/mock/settings.json";

interface SettingsStore {
  settings: AppSettings;
  updateSettings: (patch: Partial<AppSettings>) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: defaultSettings as unknown as AppSettings,
  updateSettings: (patch) =>
    set((state) => ({ settings: { ...state.settings, ...patch } })),
}));
