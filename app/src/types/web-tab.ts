export type WebTabSourceType = "portal" | "human_task" | "manual_url";

export type WebTabStatus = "loading" | "ready" | "failed" | "closed";

export type ClientOpenMode = "webcontents" | "system_browser";

export interface WebTab {
  id: string;
  title: string;
  url: string;
  favicon?: string;

  sourceType: WebTabSourceType;
  portalId?: string;
  taskId?: string;
  humanActionId?: string;

  sessionPartition: string;

  status: WebTabStatus;
  canGoBack: boolean;
  canGoForward: boolean;

  createdAt: string;
  updatedAt: string;
}

export interface OpenUrlInput {
  url: string;
  title?: string;

  sourceType: WebTabSourceType;
  portalId?: string;
  taskId?: string;
  humanActionId?: string;

  sessionPartition?: string;
  openMode?: ClientOpenMode;
}
