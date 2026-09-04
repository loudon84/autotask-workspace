import { app, type BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";
import { IPC_CHANNELS } from "@/constants";

/** 更新状态机：idle → checking → available → downloading → downloaded；任何一步失败进 error */
export interface AppUpdateState {
  status: "idle" | "checking" | "available" | "downloading" | "downloaded" | "error";
  /** available / downloading / downloaded 时的目标版本号 */
  version?: string;
  /** downloading 时的进度 0-100 */
  percent?: number;
  /** error 时的信息 */
  message?: string;
}

const FIRST_CHECK_DELAY_MS = 15_000;
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;

class AppUpdater {
  private state: AppUpdateState = { status: "idle" };
  private getWindow: (() => BrowserWindow | null) | null = null;
  private timer: NodeJS.Timeout | null = null;
  private wired = false;

  /** 只有 Windows 打包版（非绿色版）启用更新 */
  private get supported(): boolean {
    return app.isPackaged && process.platform === "win32";
  }

  getState(): AppUpdateState {
    return this.state;
  }

  setup(getWindow: () => BrowserWindow | null): void {
    this.getWindow = getWindow;
    if (!this.supported || this.wired) {
      return;
    }
    this.wired = true;

    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = false;

    autoUpdater.on("update-available", (info) => {
      this.setState({ status: "available", version: info.version });
    });
    autoUpdater.on("update-not-available", () => {
      this.setState({ status: "idle" });
    });
    autoUpdater.on("download-progress", (progress) => {
      this.setState({
        status: "downloading",
        version: this.state.version,
        percent: Math.round(progress.percent),
      });
    });
    autoUpdater.on("update-downloaded", (info) => {
      this.setState({ status: "downloaded", version: info.version });
    });
    autoUpdater.on("error", (error) => {
      // 后台检查失败保持安静，只记录状态，不弹窗
      console.error("app update error:", error);
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

  /** 退出并安装。isSilent=false, isForceRunAfter=true：安装完自动拉起 */
  install(): void {
    if (!this.supported || this.state.status !== "downloaded") {
      return;
    }
    autoUpdater.quitAndInstall(false, true);
  }

  private setState(next: AppUpdateState): void {
    this.state = next;
    this.getWindow?.()?.webContents.send(
      IPC_CHANNELS.APP_UPDATE_STATE_CHANGED,
      next
    );
  }
}

export const appUpdater = new AppUpdater();
