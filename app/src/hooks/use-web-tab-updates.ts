import { useEffect } from "react";
import { IPC_CHANNELS } from "@/constants";
import type { WebTab } from "@/types/web-tab";

export function useWebTabUpdates(onUpdate: (tab: WebTab) => void) {
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.channel !== IPC_CHANNELS.WEB_WORKSPACE_TAB_UPDATED) return;
      onUpdate(event.data.tab as WebTab);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onUpdate]);
}
