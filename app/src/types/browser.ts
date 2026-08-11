export type BrowserSessionStatus =
  | "STARTING"
  | "OPENED"
  | "ATTACHED"
  | "LOCKED"
  | "CLOSED"
  | "ERROR";

export type BrowserLaunchMode = "manual_open" | "rpa_launch" | "cdp_attach";

export type BrowserType = "chrome" | "edge" | "chromium";

export interface BrowserSession {
  id: string;
  portalId: string;
  portalName: string;
  customerName: string;

  taskId?: string;
  runId?: string;

  profileId: string;
  profilePath: string;

  browserType: BrowserType;
  launchMode: BrowserLaunchMode;

  pid?: number;
  cdpPort?: number;
  cdpEndpoint?: string;

  targetUrl: string;
  status: BrowserSessionStatus;

  lockedBy?: string;
  startedAt: string;
  lastActiveAt?: string;
  closedAt?: string;

  errorMessage?: string;
}

export interface BrowserConfig {
  defaultBrowserType: BrowserType;
  chromeExecutablePath?: string;
  edgeExecutablePath?: string;
  chromiumExecutablePath?: string;

  profileRootPath: string;

  remoteDebuggingAddress: "127.0.0.1";
  portStrategy: "random";
  minPort: number;
  maxPort: number;

  defaultOpenMode: "new_window";
  allowResetProfile: boolean;
  allowOpenProfileFolder: boolean;

  downloadsRootPath: string;
}

export type HumanCheckpointReason =
  | "captcha"
  | "mfa"
  | "manual_upload"
  | "manual_confirm"
  | "page_exception"
  | "business_check";

export type HumanCheckpointStatus =
  | "WAITING"
  | "OPENED"
  | "CONFIRMED"
  | "CANCELLED";

export interface HumanCheckpoint {
  id: string;
  taskId: string;
  runId?: string;
  stepId: string;

  portalId: string;
  targetUrl: string;

  reason: HumanCheckpointReason;
  instruction: string;
  confirmButtonText: string;

  status: HumanCheckpointStatus;

  openedSessionId?: string;
  openedAt?: string;
  confirmedAt?: string;
  confirmedBy?: string;
  note?: string;
}

export interface LoginCheckConfig {
  type: "url_contains" | "selector_visible" | "text_contains";
  value: string;
  timeoutMs: number;
}

export interface DetectedBrowser {
  browserType: BrowserType;
  name: string;
  executablePath: string;
  available: boolean;
  version: string;
}
