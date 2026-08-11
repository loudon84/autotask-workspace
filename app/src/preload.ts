import { ipcRenderer } from "electron";
import { IPC_CHANNELS } from "./constants";

window.addEventListener("message", (event) => {
  if (event.data === IPC_CHANNELS.START_ORPC_SERVER) {
    const [serverPort] = event.ports;

    ipcRenderer.postMessage(IPC_CHANNELS.START_ORPC_SERVER, null, [serverPort]);
  }
});

ipcRenderer.on(IPC_CHANNELS.WEB_WORKSPACE_TAB_UPDATED, (_event, tab) => {
  window.postMessage(
    { channel: IPC_CHANNELS.WEB_WORKSPACE_TAB_UPDATED, tab },
    "*"
  );
});
