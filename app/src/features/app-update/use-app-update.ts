import { useCallback, useEffect, useState } from "react";
import { IPC_CHANNELS } from "@/constants";
import { ipc } from "@/ipc/manager";
import type { AppUpdateState } from "@/main/app-updater";

/** 订阅主进程推送的更新状态，并暴露下载/安装动作。 */
export function useAppUpdate() {
  const [state, setState] = useState<AppUpdateState>({ status: "idle" });

  useEffect(() => {
    let mounted = true;
    ipc.client.appUpdate
      .getState()
      .then((current) => {
        if (mounted) {
          setState(current);
        }
      })
      .catch(() => {
        // 主进程尚未就绪时保持 idle
      });

    const handler = (event: MessageEvent) => {
      if (event.data?.channel !== IPC_CHANNELS.APP_UPDATE_STATE_CHANGED) {
        return;
      }
      setState(event.data.state as AppUpdateState);
    };
    window.addEventListener("message", handler);
    return () => {
      mounted = false;
      window.removeEventListener("message", handler);
    };
  }, []);

  const download = useCallback(() => ipc.client.appUpdate.download(), []);
  const install = useCallback(() => {
    void ipc.client.appUpdate.install();
  }, []);

  return { state, download, install };
}
