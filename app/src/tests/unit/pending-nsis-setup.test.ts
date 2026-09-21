import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  UPDATER_CACHE_DIR_NAME,
  WINDOWS_INSTALL_DIR,
  WINDOWS_SMC_ROOT,
  WINDOWS_SMC_UPDATES_DIR,
  findPendingSetupExe,
  isInsideInstallDir,
  isLaunchableSetupPath,
  removeStaleAutoTaskSetups,
  setupSourcesToStage,
  smcStageDirs,
  stageSetupUnderSmc,
} from "@/main/pending-nsis-setup";

describe("findPendingSetupExe", () => {
  it("没有 pending 目录时返回 null", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-updater-"));
    expect(findPendingSetupExe(root)).toBeNull();
  });

  it("找到 pending 下的 setup.exe", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-updater-"));
    const pending = path.join(root, UPDATER_CACHE_DIR_NAME, "pending");
    mkdirSync(pending, { recursive: true });
    const setup = path.join(pending, "AutoTask-Studio-0.1.6-setup.exe");
    writeFileSync(setup, "x");
    expect(findPendingSetupExe(root)).toBe(setup);
  });
});

describe("stageSetupUnderSmc", () => {
  it("拷到第一个可写的白名单目录", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-stage-"));
    const srcDir = path.join(root, "pending");
    mkdirSync(srcDir, { recursive: true });
    const setup = path.join(srcDir, "AutoTask-Studio-0.1.8-setup.exe");
    writeFileSync(setup, "x");
    const destDir = path.join(root, "SMC", "updates", "AutoTask");
    const staged = stageSetupUnderSmc(setup, [destDir]);
    expect(staged).toBe(path.join(destDir, "AutoTask-Studio-0.1.8-setup.exe"));
    expect(existsSync(staged)).toBe(true);
  });

  it("第一处不可写时试下一处", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-stage-"));
    const setup = path.join(root, "AutoTask-Studio-0.1.8-setup.exe");
    writeFileSync(setup, "x");
    const blocked = path.join(root, "blocked-file");
    writeFileSync(blocked, "nope");
    const fallback = path.join(root, "SMC");
    const staged = stageSetupUnderSmc(setup, [blocked, fallback]);
    expect(staged).toBe(path.join(fallback, "AutoTask-Studio-0.1.8-setup.exe"));
  });

  it("都不可写时返回 null", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-stage-"));
    const setup = path.join(root, "AutoTask-Studio-0.1.8-setup.exe");
    writeFileSync(setup, "x");
    const blocked = path.join(root, "blocked-file");
    writeFileSync(blocked, "nope");
    expect(stageSetupUnderSmc(setup, [blocked])).toBeNull();
  });
});

describe("ensureAutoTaskUpdatesDir", () => {
  it("创建 SMC\\updates\\AutoTask", () => {
    expect(WINDOWS_SMC_UPDATES_DIR).toBe(
      path.join(WINDOWS_SMC_ROOT, "updates", "AutoTask")
    );
    expect(smcStageDirs()).toEqual([WINDOWS_SMC_UPDATES_DIR, WINDOWS_SMC_ROOT]);
  });
});

describe("isLaunchableSetupPath", () => {
  it("安装目录里不可启动，SMC 根和 updates\\AutoTask 可以", () => {
    expect(
      isLaunchableSetupPath(
        path.join(WINDOWS_SMC_UPDATES_DIR, "AutoTask-Studio-0.1.23-setup.exe")
      )
    ).toBe(true);
    expect(
      isLaunchableSetupPath(
        path.join(WINDOWS_SMC_ROOT, "AutoTask-Studio-0.1.23-setup.exe")
      )
    ).toBe(true);
    expect(
      isLaunchableSetupPath(path.join(WINDOWS_INSTALL_DIR, "updates", "a.exe"))
    ).toBe(false);
    expect(isInsideInstallDir(path.join(WINDOWS_INSTALL_DIR, "updates"))).toBe(
      true
    );
    expect(
      isLaunchableSetupPath(
        "C:\\Users\\x\\AppData\\Local\\AutoTask-updater\\pending\\a.exe"
      )
    ).toBe(false);
  });
});

describe("removeStaleAutoTaskSetups", () => {
  it("只删 AutoTask 的旧 setup，保留正在用的和其它文件", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-stale-"));
    const keep = path.join(root, "AutoTask-Studio-0.1.23-setup.exe");
    const old = path.join(root, "AutoTask-Studio-0.1.22-setup.exe");
    const other = path.join(root, "SMC-DESP-setup.exe");
    writeFileSync(keep, "keep");
    writeFileSync(old, "old");
    writeFileSync(other, "other");
    removeStaleAutoTaskSetups(keep, [root]);
    expect(existsSync(keep)).toBe(true);
    expect(existsSync(old)).toBe(false);
    expect(existsSync(other)).toBe(true);
  });
});

describe("setupSourcesToStage", () => {
  it("把 pending 里的包列为拷贝来源", () => {
    const root = mkdtempSync(path.join(os.tmpdir(), "at-src-"));
    const pending = path.join(root, UPDATER_CACHE_DIR_NAME, "pending");
    mkdirSync(pending, { recursive: true });
    writeFileSync(path.join(pending, "AutoTask-Studio-0.1.11-setup.exe"), "x");
    const sources = setupSourcesToStage(root);
    expect(
      sources.some((file) => file.endsWith("AutoTask-Studio-0.1.11-setup.exe"))
    ).toBe(true);
  });
});
