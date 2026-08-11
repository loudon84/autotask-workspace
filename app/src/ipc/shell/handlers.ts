import { os } from "@orpc/server";
import { shell } from "electron";
import { ipcContext } from "@/ipc/context";
import {
  downloadFileInputSchema,
  openExternalLinkInputSchema,
} from "./schemas";

export const openExternalLink = os
  .input(openExternalLinkInputSchema)
  .handler(({ input }) => {
    const { url } = input;
    shell.openExternal(url);
  });

export const downloadFile = os
  .input(downloadFileInputSchema)
  .use(ipcContext.mainWindowContext)
  .handler(({ context, input }) => {
    context.window.webContents.downloadURL(input.url);
  });
