import { create } from "zustand";

type PortalWritePermissionState = {
  canWrite: boolean;
  markForbidden: () => void;
  reset: () => void;
};

export const usePortalWritePermission = create<PortalWritePermissionState>(
  (set) => ({
    canWrite: true,
    markForbidden: () => set({ canWrite: false }),
    reset: () => set({ canWrite: true }),
  })
);
