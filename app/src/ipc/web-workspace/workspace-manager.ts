import {
  type BrowserWindow,
  type WebContentsView,
  WebContentsView as WebContentsViewClass,
  shell,
} from "electron";
import { IPC_CHANNELS } from "@/constants";
import type { WebTab } from "@/types/web-tab";
import { tabStore } from "./tab-store";
import { getSession, resolvePartition, validateUrl } from "./session-manager";

interface ManagedView {
  view: WebContentsView;
  tabId: string;
}

class WebWorkspaceManager {
  private mainWindow: BrowserWindow | undefined;
  private views = new Map<string, ManagedView>();
  private bounds = { x: 0, y: 0, width: 800, height: 600 };
  private visible = false;

  setMainWindow(window: BrowserWindow) {
    this.mainWindow = window;
    window.on("resize", () => this.applyBounds());
  }

  setBounds(bounds: { x: number; y: number; width: number; height: number }) {
    this.bounds = bounds;
    this.applyBounds();
  }

  setVisibility(visible: boolean) {
    this.visible = visible;
    for (const { view } of this.views.values()) {
      view.setVisible(visible && this.isActiveView(view));
    }
  }

  private isActiveView(view: WebContentsView): boolean {
    const activeId = tabStore.getActiveId();
    if (!activeId) return false;
    const managed = this.views.get(activeId);
    return managed?.view === view;
  }

  private applyBounds() {
    const activeId = tabStore.getActiveId();
    if (!activeId) return;
    const managed = this.views.get(activeId);
    if (!managed) return;
    managed.view.setBounds({
      x: Math.round(this.bounds.x),
      y: Math.round(this.bounds.y),
      width: Math.max(0, Math.round(this.bounds.width)),
      height: Math.max(0, Math.round(this.bounds.height)),
    });
  }

  private emitTabUpdate(tab: WebTab) {
    this.mainWindow?.webContents.send(IPC_CHANNELS.WEB_WORKSPACE_TAB_UPDATED, tab);
  }

  private createView(tab: WebTab): WebContentsView {
    const ses = getSession(tab.sessionPartition);
    const view = new WebContentsViewClass({
      webPreferences: {
        session: ses,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });

    const wc = view.webContents;

    wc.setWindowOpenHandler(({ url }) => {
      shell.openExternal(url).catch(() => undefined);
      return { action: "deny" };
    });

    ses.setPermissionRequestHandler((_webContents, permission, callback) => {
      const allowed = ["clipboard-read", "clipboard-sanitized-write"].includes(permission);
      callback(allowed);
    });

    ses.setPermissionCheckHandler((_webContents, permission) => {
      return ["clipboard-read", "clipboard-sanitized-write"].includes(permission);
    });

    wc.on("will-navigate", (event, url) => {
      try {
        validateUrl(url);
      } catch {
        event.preventDefault();
      }
    });

    wc.on("did-start-loading", () => {
      const updated = tabStore.update(tab.id, { status: "loading" });
      if (updated) this.emitTabUpdate(updated);
    });

    wc.on("did-finish-load", () => {
      const updated = tabStore.update(tab.id, {
        status: "ready",
        url: wc.getURL(),
        title: wc.getTitle() || tab.title,
        canGoBack: wc.navigationHistory.canGoBack(),
        canGoForward: wc.navigationHistory.canGoForward(),
      });
      if (updated) this.emitTabUpdate(updated);
    });

    wc.on("did-fail-load", () => {
      const updated = tabStore.update(tab.id, { status: "failed" });
      if (updated) this.emitTabUpdate(updated);
    });

    wc.on("did-navigate", () => {
      const updated = tabStore.update(tab.id, {
        url: wc.getURL(),
        canGoBack: wc.navigationHistory.canGoBack(),
        canGoForward: wc.navigationHistory.canGoForward(),
      });
      if (updated) this.emitTabUpdate(updated);
    });

    wc.on("page-title-updated", (_event, title) => {
      const updated = tabStore.update(tab.id, { title: title || tab.title });
      if (updated) this.emitTabUpdate(updated);
    });

    wc.on("page-favicon-updated", (_event, favicons) => {
      const favicon = favicons[0];
      if (!favicon) return;
      const updated = tabStore.update(tab.id, { favicon });
      if (updated) this.emitTabUpdate(updated);
    });

    return view;
  }

  private attachView(tab: WebTab) {
    if (!this.mainWindow) throw new Error("主窗口未初始化");

    let managed = this.views.get(tab.id);
    if (!managed) {
      const view = this.createView(tab);
      this.mainWindow.contentView.addChildView(view);
      managed = { view, tabId: tab.id };
      this.views.set(tab.id, managed);
    }

    for (const entry of this.views.values()) {
      entry.view.setVisible(false);
    }

    managed.view.setVisible(this.visible);
    this.applyBounds();
    validateUrl(tab.url);
    managed.view.webContents.loadURL(tab.url).catch(() => {
      const updated = tabStore.update(tab.id, { status: "failed" });
      if (updated) this.emitTabUpdate(updated);
    });
  }

  openUrl(input: {
    url: string;
    title?: string;
    sourceType: WebTab["sourceType"];
    portalId?: string;
    taskId?: string;
    humanActionId?: string;
    sessionPartition?: string;
    openMode?: "webcontents" | "system_browser";
  }): WebTab {
    validateUrl(input.url);

    if (input.openMode === "system_browser") {
      shell.openExternal(input.url).catch(() => undefined);
      const tab = tabStore.create({
        title: input.title ?? input.url,
        url: input.url,
        sourceType: input.sourceType,
        portalId: input.portalId,
        taskId: input.taskId,
        humanActionId: input.humanActionId,
        sessionPartition: resolvePartition(input.sessionPartition),
      });
      this.emitTabUpdate(tab);
      return tab;
    }

    const existing = tabStore.findExisting({
      portalId: input.portalId,
      taskId: input.taskId,
      url: input.url,
      sourceType: input.sourceType,
    });
    if (existing) {
      tabStore.activate(existing.id);
      this.showTab(existing.id);
      return tabStore.get(existing.id)!;
    }

    const tab = tabStore.create({
      title: input.title ?? input.url,
      url: input.url,
      sourceType: input.sourceType,
      portalId: input.portalId,
      taskId: input.taskId,
      humanActionId: input.humanActionId,
      sessionPartition: resolvePartition(input.sessionPartition),
    });

    this.attachView(tab);
    this.emitTabUpdate(tab);
    return tab;
  }

  private showTab(tabId: string) {
    const tab = tabStore.get(tabId);
    if (!tab) return;
    tabStore.activate(tabId);
    this.attachView(tab);
    this.emitTabUpdate(tab);
  }

  activateTab(tabId: string): WebTab {
    const tab = tabStore.get(tabId);
    if (!tab || tab.status === "closed") throw new Error("Tab 不存在");
    this.showTab(tabId);
    return tab;
  }

  closeTab(tabId: string): void {
    const managed = this.views.get(tabId);
    if (managed && this.mainWindow) {
      this.mainWindow.contentView.removeChildView(managed.view);
      managed.view.webContents.close();
      this.views.delete(tabId);
    }
    tabStore.close(tabId);
    const active = tabStore.getActive();
    if (active) {
      this.showTab(active.id);
    }
  }

  reload(tabId: string): void {
    const managed = this.views.get(tabId);
    if (!managed) throw new Error("Tab 不存在");
    managed.view.webContents.reload();
  }

  goBack(tabId: string): void {
    const managed = this.views.get(tabId);
    if (!managed) throw new Error("Tab 不存在");
    if (managed.view.webContents.navigationHistory.canGoBack()) {
      managed.view.webContents.navigationHistory.goBack();
    }
  }

  goForward(tabId: string): void {
    const managed = this.views.get(tabId);
    if (!managed) throw new Error("Tab 不存在");
    if (managed.view.webContents.navigationHistory.canGoForward()) {
      managed.view.webContents.navigationHistory.goForward();
    }
  }

  copyUrl(tabId: string): string {
    const tab = tabStore.get(tabId);
    if (!tab) throw new Error("Tab 不存在");
    return tab.url;
  }

  listTabs(): WebTab[] {
    return tabStore.list();
  }

  getActiveTab(): WebTab | null {
    return tabStore.getActive();
  }
}

export const webWorkspaceManager = new WebWorkspaceManager();
