import { ipc } from "@/ipc/manager";
import type { OpenUrlInput } from "@/types/web-tab";

export function initWebWorkspace() {
  return ipc.client.webWorkspace.initWorkspace();
}

export function openUrl(input: OpenUrlInput) {
  return ipc.client.webWorkspace.openUrl(input);
}

export function openPortal(input: {
  portalId: string;
  url: string;
  title?: string;
  sessionPartition: string;
  openMode?: "webcontents" | "system_browser";
}) {
  return ipc.client.webWorkspace.openPortal(input);
}

export function openHumanTask(input: {
  taskId: string;
  humanActionId?: string;
  url: string;
  title?: string;
  portalId?: string;
  sessionPartition?: string;
}) {
  return ipc.client.webWorkspace.openHumanTask(input);
}

export function closeTab(tabId: string) {
  return ipc.client.webWorkspace.closeTab({ tabId });
}

export function activateTab(tabId: string) {
  return ipc.client.webWorkspace.activateTab({ tabId });
}

export function reloadTab(tabId: string) {
  return ipc.client.webWorkspace.reload({ tabId });
}

export function goBack(tabId: string) {
  return ipc.client.webWorkspace.goBack({ tabId });
}

export function goForward(tabId: string) {
  return ipc.client.webWorkspace.goForward({ tabId });
}

export function copyUrl(tabId: string) {
  return ipc.client.webWorkspace.copyUrl({ tabId });
}

export function openExternal(url: string) {
  return ipc.client.webWorkspace.openExternal({ url });
}

export function listTabs() {
  return ipc.client.webWorkspace.listTabs();
}

export function getActiveTab() {
  return ipc.client.webWorkspace.getActiveTab();
}

export function setWorkspaceBounds(bounds: {
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  return ipc.client.webWorkspace.setBounds(bounds);
}

export function setWorkspaceVisibility(visible: boolean) {
  return ipc.client.webWorkspace.setVisibility({ visible });
}

export function clearPortalSession(partition: string) {
  return ipc.client.webWorkspace.clearPortalSession({ partition });
}

export function clearAllWebSessions() {
  return ipc.client.webWorkspace.clearAllSessions();
}
