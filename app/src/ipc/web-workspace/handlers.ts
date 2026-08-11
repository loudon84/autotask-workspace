import { os } from "@orpc/server";
import { shell } from "electron";
import { ipcContext } from "@/ipc/context";
import { clearAllWebSessions, clearSession, validateUrl } from "./session-manager";
import {
  clearSessionInputSchema,
  openExternalInputSchema,
  openHumanTaskInputSchema,
  openPortalInputSchema,
  openUrlInputSchema,
  setBoundsInputSchema,
  setVisibilityInputSchema,
  tabIdInputSchema,
} from "./schemas";
import { resolvePartition } from "./session-manager";
import { webWorkspaceManager } from "./workspace-manager";

export const openUrl = os
  .input(openUrlInputSchema)
  .handler(({ input }) => webWorkspaceManager.openUrl(input));

export const openPortal = os
  .input(openPortalInputSchema)
  .handler(({ input }) =>
    webWorkspaceManager.openUrl({
      url: input.url,
      title: input.title,
      sourceType: "portal",
      portalId: input.portalId,
      sessionPartition: input.sessionPartition,
      openMode: input.openMode,
    })
  );

export const openHumanTask = os
  .input(openHumanTaskInputSchema)
  .handler(({ input }) =>
    webWorkspaceManager.openUrl({
      url: input.url,
      title: input.title,
      sourceType: "human_task",
      taskId: input.taskId,
      humanActionId: input.humanActionId,
      portalId: input.portalId,
      sessionPartition: input.sessionPartition ?? `persist:task:${input.taskId}`,
      openMode: "webcontents",
    })
  );

export const closeTab = os
  .input(tabIdInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.closeTab(input.tabId);
  });

export const activateTab = os
  .input(tabIdInputSchema)
  .handler(({ input }) => webWorkspaceManager.activateTab(input.tabId));

export const reload = os
  .input(tabIdInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.reload(input.tabId);
  });

export const goBack = os
  .input(tabIdInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.goBack(input.tabId);
  });

export const goForward = os
  .input(tabIdInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.goForward(input.tabId);
  });

export const copyUrl = os
  .input(tabIdInputSchema)
  .handler(({ input }) => webWorkspaceManager.copyUrl(input.tabId));

export const listTabs = os.handler(() => webWorkspaceManager.listTabs());

export const getActiveTab = os.handler(() => webWorkspaceManager.getActiveTab());

export const setBounds = os
  .input(setBoundsInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.setBounds(input);
  });

export const setVisibility = os
  .input(setVisibilityInputSchema)
  .handler(({ input }) => {
    webWorkspaceManager.setVisibility(input.visible);
  });

export const openExternal = os
  .input(openExternalInputSchema)
  .handler(async ({ input }) => {
    validateUrl(input.url);
    await shell.openExternal(input.url);
  });

export const clearPortalSession = os
  .input(clearSessionInputSchema)
  .handler(async ({ input }) => {
    await clearSession(input.partition);
    return { success: true };
  });

export const clearAllSessions = os.handler(async () => {
  await clearAllWebSessions();
  return { success: true };
});

export const initWorkspace = os.handler(() => {
  const window = ipcContext.mainWindow;
  if (window) {
    webWorkspaceManager.setMainWindow(window);
  }
  return { success: true };
});
