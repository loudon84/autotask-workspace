import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  statSync,
  unlinkSync,
} from "node:fs";
import path from "node:path";

/** 与 app-update.yml 的 updaterCacheDirName 一致 */
export const UPDATER_CACHE_DIR_NAME = "AutoTask-updater";

/** 杀毒白名单根目录；桌面端约定装在此路径下 */
export const WINDOWS_SMC_ROOT = "D:\\Programs\\SMC";

/** 与 NSIS 默认安装目录一致。安装包不能放在这里面，重装会清掉整个目录。 */
export const WINDOWS_INSTALL_DIR = "D:\\Programs\\SMC\\AutoTask";

/** 各产品自己的更新目录：SMC\updates\<产品>，互不影响。 */
// @lat: [[client#Online Updates#Staging outside the install directory]]
export const WINDOWS_SMC_UPDATES_DIR = path.join(
  WINDOWS_SMC_ROOT,
  "updates",
  "AutoTask"
);

export function ensureAutoTaskUpdatesDir(): string {
  mkdirSync(WINDOWS_SMC_UPDATES_DIR, { recursive: true });
  return WINDOWS_SMC_UPDATES_DIR;
}

const AUTOTASK_SETUP_NAME = /^AutoTask-Studio-.+-setup\.exe$/i;

function normalizePath(filePath: string): string {
  return path.normalize(filePath).toLowerCase();
}

/** 优先产品更新目录；杀毒若拦子目录再退回 SMC 根。都不在安装目录里。 */
export function smcStageDirs(): string[] {
  return [WINDOWS_SMC_UPDATES_DIR, WINDOWS_SMC_ROOT];
}

export function isUnderSmc(filePath: string): boolean {
  const normalized = normalizePath(filePath);
  const root = normalizePath(WINDOWS_SMC_ROOT).replace(/[\\/]+$/, "");
  return normalized === root || normalized.startsWith(`${root}${path.sep}`);
}

export function isInsideInstallDir(filePath: string): boolean {
  const normalized = normalizePath(filePath);
  const inst = normalizePath(WINDOWS_INSTALL_DIR);
  return normalized === inst || normalized.startsWith(`${inst}${path.sep}`);
}

/** 在 SMC 下、且不在即将被重装清空的 AutoTask 安装目录里。 */
export function isLaunchableSetupPath(filePath: string): boolean {
  return isUnderSmc(filePath) && !isInsideInstallDir(filePath);
}

function findSetupExeInDir(dir: string): string | null {
  if (!existsSync(dir)) {
    return null;
  }
  const name = readdirSync(dir).find((file) => AUTOTASK_SETUP_NAME.test(file));
  return name == null ? null : path.join(dir, name);
}

/** AppData pending，以及历史误放的包，都作为拷到更新目录的来源。 */
export function setupSourcesToStage(localAppData: string): string[] {
  const sources = [
    findPendingSetupExe(localAppData),
    findSetupExeInDir(WINDOWS_SMC_UPDATES_DIR),
    findSetupExeInDir(WINDOWS_SMC_ROOT),
    findSetupExeInDir(path.join(WINDOWS_INSTALL_DIR, "updates")),
  ];
  return sources.filter((file): file is string => file != null);
}

/** 在 LocalAppData 缓存里找到已下载的 NSIS 安装包。 */
export function findPendingSetupExe(localAppData: string): string | null {
  const pending = path.join(localAppData, UPDATER_CACHE_DIR_NAME, "pending");
  if (!existsSync(pending)) {
    return null;
  }
  const name = readdirSync(pending).find((file) => AUTOTASK_SETUP_NAME.test(file));
  return name == null ? null : path.join(pending, name);
}

/** 把 setup.exe 拷到 SMC 更新目录（或根目录兜底）。失败返回 null。 */
export function stageSetupUnderSmc(
  setupPath: string,
  destDirs: string[] = smcStageDirs()
): string | null {
  const name = path.basename(setupPath);
  let sourceSize = 0;
  try {
    sourceSize = statSync(setupPath).size;
  } catch {
    return null;
  }
  for (const dir of destDirs) {
    const dest = path.join(dir, name);
    if (!copySetupFile(setupPath, dest)) {
      continue;
    }
    try {
      unlinkSync(`${dest}:Zone.Identifier`);
    } catch {
      // 没有 MOTW 流时忽略
    }
    try {
      if (statSync(dest).size !== sourceSize) {
        continue;
      }
    } catch {
      continue;
    }
    return dest;
  }
  return null;
}

/** 只删 AutoTask 自己的 setup，保留 keepPath（正在启动的那份）。 */
export function removeStaleAutoTaskSetups(
  keepPath: string,
  dirs: string[] = [
    WINDOWS_SMC_UPDATES_DIR,
    WINDOWS_SMC_ROOT,
    path.join(WINDOWS_INSTALL_DIR, "updates"),
  ]
): void {
  const keep = normalizePath(keepPath);
  for (const dir of dirs) {
    if (!existsSync(dir)) {
      continue;
    }
    let names: string[] = [];
    try {
      names = readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of names) {
      if (!AUTOTASK_SETUP_NAME.test(name)) {
        continue;
      }
      const full = path.join(dir, name);
      if (normalizePath(full) === keep) {
        continue;
      }
      try {
        unlinkSync(full);
      } catch {
        // 文件占用时下次再清
      }
    }
  }
}

function copySetupFile(setupPath: string, dest: string): boolean {
  try {
    mkdirSync(path.dirname(dest), { recursive: true });
    copyFileSync(setupPath, dest);
    return existsSync(dest);
  } catch {
    // Node 拷贝可能被拦，改用 cmd copy（父进程是 SMC 目录下的 AutoTask）
  }
  try {
    mkdirSync(path.dirname(dest), { recursive: true });
    const copied = spawnSync(
      "cmd.exe",
      ["/c", `copy /Y "${setupPath}" "${dest}"`],
      { windowsVerbatimArguments: true, stdio: "ignore" }
    );
    return copied.status === 0 && existsSync(dest);
  } catch {
    return false;
  }
}
