import { appendFileSync, mkdirSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { app, BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";
import { IPC_CHANNELS } from "@/constants";
import {
  ensureAutoTaskUpdatesDir,
  findPendingSetupExe,
  isLaunchableSetupPath,
  removeStaleAutoTaskSetups,
  setupSourcesToStage,
  stageSetupUnderSmc,
} from "@/main/pending-nsis-setup";
import { nsisUpdateStartCommand, NSIS_UPDATE_ARGS } from "@/main/delayed-setup-launch";

/** 与 NSIS maker / app-update.yml 同一地址；打包后 yml 缺失时仍能检查更新 */
const UPDATE_FEED_URL = "https://release.superic.com/autotask/stable/";

function logUpdate(message: string, error?: unknown): void {
  const text = error == null ? message : `${message} ${String(error)}`;
  console.error("app update:", text);
  try {
    const dir = path.join(app.getPath("userData"), "logs");
    mkdirSync(dir, { recursive: true });
    appendFileSync(
      path.join(dir, "updater.log"),
      `${new Date().toISOString()} ${text}\n`
    );
  } catch {
    // 写日志失败不影响更新
  }
}

function waitForSpawn(
  command: string,
  args: string[],
  options: Parameters<typeof spawn>[2]
): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, options);
    let settled = false;
    const finish = (error?: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      child.unref();
      if (error) {
        reject(error);
        return;
      }
      resolve();
    };
    child.once("error", (error) => {
      finish(error instanceof Error ? error : new Error(String(error)));
    });
    child.once("spawn", () => {
      finish();
    });
  });
}

/**
 * 独立拉起 NSIS：`--updated` 跳过选目录，`--force-run` 装完再打开。
 * 不用 `/S`，安装窗口要显示进度。启动失败则保持当前版本可用。
 */
async function launchSetupExe(setupPath: string): Promise<void> {
  const args = [...NSIS_UPDATE_ARGS];
  logUpdate(`quitAndInstall ${setupPath} ${args.join(" ")}`);
  try {
    await waitForSpawn(setupPath, args, {
      detached: true,
      stdio: "ignore",
      cwd: path.dirname(setupPath),
    });
    return;
  } catch (error) {
    logUpdate("detached setup spawn failed", error);
  }
  try {
    await waitForSpawn("cmd.exe", ["/c", nsisUpdateStartCommand(setupPath)], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
      windowsVerbatimArguments: true,
      cwd: path.dirname(setupPath),
    });
  } catch (error) {
    logUpdate("cmd start update failed", error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/** 更新状态机：idle → checking → available → downloading → downloaded；已是最新为 uptodate */
export interface AppUpdateState {
  status:
    | "idle"
    | "checking"
    | "available"
    | "downloading"
    | "downloaded"
    | "uptodate"
    | "error";
  /** available / downloading / downloaded 时的目标版本号 */
  version?: string;
  /** downloading 时的进度 0-100 */
  percent?: number;
  /** error 时的信息 */
  message?: string;
  /** 仅 Windows 打包版为 true */
  supported?: boolean;
}

const FIRST_CHECK_DELAY_MS = 15_000;
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;

// @lat: [[client#Online Updates]]
class AppUpdater {
  private state: AppUpdateState = { status: "idle" };
  private getWindow: (() => BrowserWindow | null) | null = null;
  private timer: NodeJS.Timeout | null = null;
  private wired = false;
  private installWhenDownloaded = false;
  private stagedSetupPath: string | null = null;

  /** 只有 Windows 打包版（非绿色版）启用更新 */
  private get supported(): boolean {
    return app.isPackaged && process.platform === "win32";
  }

  getState(): AppUpdateState {
    return { ...this.state, supported: this.supported };
  }

  setup(getWindow: () => BrowserWindow | null): void {
    this.getWindow = getWindow;
    if (!this.supported || this.wired) {
      return;
    }
    this.wired = true;
    try {
      ensureAutoTaskUpdatesDir();
    } catch (error) {
      logUpdate("ensure updates dir failed", error);
    }

    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = false;
    autoUpdater.disableWebInstaller = true;
    autoUpdater.setFeedURL({
      provider: "generic",
      url: UPDATE_FEED_URL,
    });
    autoUpdater.logger = {
      info: (message) => logUpdate(String(message)),
      warn: (message) => logUpdate(String(message)),
      error: (message) => logUpdate(String(message)),
      debug: (message) => logUpdate(String(message)),
    };

    autoUpdater.on("update-available", (info) => {
      this.setState({ status: "available", version: info.version });
    });
    autoUpdater.on("update-not-available", () => {
      this.setState({ status: "uptodate" });
    });
    autoUpdater.on("download-progress", (progress) => {
      this.setState({
        status: "downloading",
        version: this.state.version,
        percent: Math.round(progress.percent),
      });
    });
    autoUpdater.on("update-downloaded", (info) => {
      this.stagedSetupPath = this.stagePendingSetup();
      this.setState({ status: "downloaded", version: info.version });
      if (this.installWhenDownloaded) {
        this.installWhenDownloaded = false;
        void this.install();
      }
    });
    autoUpdater.on("error", (error) => {
      logUpdate("updater error", error);
      this.setState({ status: "error", message: String(error?.message ?? error) });
    });

    // 启动后 15 秒首查，之后每 6 小时一次
    this.timer = setTimeout(() => {
      void this.check();
      this.timer = setInterval(() => void this.check(), CHECK_INTERVAL_MS);
    }, FIRST_CHECK_DELAY_MS);
  }

  /** 检查更新。不支持的环境直接返回当前状态。 */
  async check(): Promise<AppUpdateState> {
    if (!this.supported) {
      return this.state;
    }
    this.setState({ status: "checking" });
    try {
      await autoUpdater.checkForUpdates();
    } catch (error) {
      // error 事件已处理状态；这里只兜底
      console.error("checkForUpdates failed:", error);
    }
    return this.state;
  }

  async download(): Promise<AppUpdateState> {
    if (!this.supported || this.state.status !== "available") {
      return this.state;
    }
    this.setState({ status: "downloading", version: this.state.version, percent: 0 });
    try {
      await autoUpdater.downloadUpdate();
    } catch (error) {
      console.error("downloadUpdate failed:", error);
    }
    return this.state;
  }

  /** 用户确认更新：下载完成后静默安装并重启 */
  async downloadAndInstall(): Promise<AppUpdateState> {
    this.installWhenDownloaded = true;
    if (this.state.status === "downloaded") {
      await this.install();
      return this.state;
    }
    return this.download();
  }

  /** 拷到 SMC\\updates\\AutoTask 后启动。只有安装程序拉起成功才关闭客户端。 */
  async install(): Promise<void> {
    if (!this.supported || this.state.status !== "downloaded") {
      logUpdate(`install ignored, status=${this.state.status}`);
      return;
    }
    logUpdate("install requested");
    this.installWhenDownloaded = false;

    const pendingPath = findPendingSetupExe(process.env.LOCALAPPDATA ?? "");
    const launchPath = this.stagedSetupPath ?? this.stagePendingSetup();
    if (pendingPath == null && launchPath == null) {
      logUpdate("install failed: pending setup.exe not found");
      this.setState({
        status: "error",
        message: "未找到已下载的安装包，请稍后重试。",
      });
      return;
    }
    logUpdate(`launch setup from ${launchPath ?? pendingPath}`);

    if (launchPath == null || !isLaunchableSetupPath(launchPath)) {
      logUpdate(`copy outside install dir failed, staged=${launchPath}`);
      this.setState({
        status: "error",
        message: "无法复制到更新目录，更新未开始。",
      });
      return;
    }

    try {
      await launchSetupExe(launchPath);
    } catch (error) {
      logUpdate("launch setup failed", error);
      this.setState({
        status: "error",
        message: "未能开始安装，当前版本仍可使用。",
      });
      return;
    }

    removeStaleAutoTaskSetups(launchPath);
    logUpdate("installer started, quitting client");
    app.quit();
  }

  private setState(next: AppUpdateState): void {
    this.state = { ...next, supported: this.supported };
    this.getWindow?.()?.webContents.send(
      IPC_CHANNELS.APP_UPDATE_STATE_CHANGED,
      this.state
    );
  }

  private stagePendingSetup(): string | null {
    const sources = setupSourcesToStage(process.env.LOCALAPPDATA ?? "");
    for (const setupPath of sources) {
      const staged = stageSetupUnderSmc(setupPath);
      logUpdate(`staged setup ${setupPath} -> ${staged}`);
      if (staged != null && isLaunchableSetupPath(staged)) {
        return staged;
      }
    }
    return null;
  }
}

export const appUpdater = new AppUpdater();
