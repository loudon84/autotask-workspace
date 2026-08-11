import type { ClientOpenMode } from "@/types/web-tab";

export interface AppSettings {
  defaultBrowserType: "chrome" | "edge" | "chromium";
  defaultRunMode: "headed" | "headless";
  saveScreenshots: boolean;
  enableTrace: boolean;
  artifactPath: string;
  logLevel: "DEBUG" | "INFO" | "WARN" | "ERROR";
  themeMode: "light" | "dark" | "system";
  mockDelayMs: number;

  defaultOpenMode: ClientOpenMode;
  allowResetSession: boolean;
  allowClearAllCache: boolean;

  chromeExecutablePath?: string;
  edgeExecutablePath?: string;
  chromiumExecutablePath?: string;
  profileRootPath: string;
  downloadsRootPath: string;
  remoteDebuggingAddress: "127.0.0.1";
  minPort: number;
  maxPort: number;
  allowResetProfile: boolean;
  allowOpenProfileFolder: boolean;
}
