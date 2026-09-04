import type { ClientOpenMode } from "@/types/web-tab";

/** 服务器调度器配置（autotask_settings，保存后热生效） */
export interface SignPollSchedulerSettings {
  enabled: boolean;
  /** 5 段 cron（分 时 日 月 周，本地时间），例：星/30 星 星 星 星 表示每半小时 */
  cron: string;
}

export interface ScanSchedulerSettings {
  enabled: boolean;
  /** 5 段 cron（分 时 日 月 周，本地时间），例：0 8 星 星 星 表示每天 8 点 */
  cron: string;
}

export interface BoePackSchedulerSettings {
  enabled: boolean;
  /** 5 段 cron（分 时 日 月 周，本地时间），例：0 7 星 星 星 表示每天 7 点 */
  cron: string;
}

export interface SchedulerSettings {
  signPoll: SignPollSchedulerSettings;
  scan: ScanSchedulerSettings;
  boePack: BoePackSchedulerSettings;
  /** 各调度器下次触发时刻（ISO 本地时间）；未启用为 null */
  nextRunAt: {
    signPoll: string | null;
    scan: string | null;
    boePack: string | null;
  };
}

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
