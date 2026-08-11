import type { WebTab, WebTabStatus } from "@/types/web-tab";

function now() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

let tabCounter = 0;

export function createTabId(): string {
  tabCounter += 1;
  return `tab_${Date.now()}_${tabCounter}`;
}

export class TabStore {
  private tabs = new Map<string, WebTab>();
  private activeTabId: string | null = null;

  list(): WebTab[] {
    return Array.from(this.tabs.values()).filter((t) => t.status !== "closed");
  }

  get(tabId: string): WebTab | undefined {
    return this.tabs.get(tabId);
  }

  getActive(): WebTab | null {
    if (!this.activeTabId) return null;
    const tab = this.tabs.get(this.activeTabId);
    return tab && tab.status !== "closed" ? tab : null;
  }

  getActiveId(): string | null {
    return this.activeTabId;
  }

  create(input: Omit<WebTab, "id" | "createdAt" | "updatedAt" | "status" | "canGoBack" | "canGoForward">): WebTab {
    const tab: WebTab = {
      ...input,
      id: createTabId(),
      status: "loading",
      canGoBack: false,
      canGoForward: false,
      createdAt: now(),
      updatedAt: now(),
    };
    this.tabs.set(tab.id, tab);
    this.activeTabId = tab.id;
    return tab;
  }

  findExisting(input: {
    portalId?: string;
    taskId?: string;
    url: string;
    sourceType: WebTab["sourceType"];
  }): WebTab | undefined {
    return this.list().find((tab) => {
      if (input.portalId && tab.portalId === input.portalId) return true;
      if (input.taskId && tab.taskId === input.taskId) return true;
      if (input.sourceType === "manual_url" && tab.url === input.url) return true;
      return false;
    });
  }

  update(tabId: string, patch: Partial<WebTab>): WebTab | undefined {
    const existing = this.tabs.get(tabId);
    if (!existing) return undefined;
    const updated: WebTab = {
      ...existing,
      ...patch,
      updatedAt: now(),
    };
    this.tabs.set(tabId, updated);
    return updated;
  }

  activate(tabId: string): WebTab | undefined {
    const tab = this.tabs.get(tabId);
    if (!tab || tab.status === "closed") return undefined;
    this.activeTabId = tabId;
    return tab;
  }

  close(tabId: string): void {
    const tab = this.tabs.get(tabId);
    if (!tab) return;
    this.tabs.set(tabId, { ...tab, status: "closed" as WebTabStatus, updatedAt: now() });
    if (this.activeTabId === tabId) {
      const remaining = this.list();
      this.activeTabId = remaining.length > 0 ? remaining[remaining.length - 1]!.id : null;
    }
  }
}

export const tabStore = new TabStore();
