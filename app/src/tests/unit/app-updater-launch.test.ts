import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  NSIS_UPDATE_ARGS,
  nsisUpdateStartCommand,
} from "@/main/delayed-setup-launch";

const src = readFileSync(
  path.resolve(__dirname, "../../main/app-updater.ts"),
  "utf8"
);
const nsh = readFileSync(
  path.resolve(__dirname, "../../../installer/install-dir.nsh"),
  "utf8"
);

describe("nsisUpdateStartCommand", () => {
  it("带 --updated --force-run，显示安装进度，不用静默 /S", () => {
    expect([...NSIS_UPDATE_ARGS]).toEqual(["--updated", "--force-run"]);
    expect(NSIS_UPDATE_ARGS).not.toContain("/S");
    expect(
      nsisUpdateStartCommand(
        "D:\\Programs\\SMC\\AutoTask-Studio-0.1.20-setup.exe"
      )
    ).toBe(
      'start "" "D:\\Programs\\SMC\\AutoTask-Studio-0.1.20-setup.exe" --updated --force-run'
    );
  });
});

describe("app-updater launch", () => {
  it("从 SMC\\updates\\AutoTask 独立拉起安装包，不用 elevate.exe", () => {
    expect(src).toContain("detached: true");
    expect(src).toContain("quitAndInstall");
    expect(src).toContain("--force-run");
    expect(src).toContain("removeStaleAutoTaskSetups");
    expect(src).toContain("ensureAutoTaskUpdatesDir");
    expect(src).not.toContain("elevate.exe");
  });

  it("安装程序拉起成功后 app.quit，失败不退出", () => {
    expect(src).toContain("app.quit()");
    expect(src).toContain("installer started, quitting client");
    expect(src).not.toMatch(/app\.exit/);
  });
});

describe("NSIS include", () => {
  it("经 explorer 再启动，避免关客户端时把安装程序一起杀掉", () => {
    expect(nsh).toContain("/autotask-detached");
    expect(nsh).toContain("explorer.exe");
    expect(nsh).toContain("autotask-relaunch.cmd");
    expect(nsh).not.toContain("customCheckAppRunning");
    expect(nsh).not.toContain('CreateDirectory "$INSTDIR\\updates"');
  });

  it("快捷方式指向 AutoTaskStudio.exe，安装目录仍是 AutoTask 一层", () => {
    const maker = readFileSync(
      path.resolve(__dirname, "../../../forge/maker-nsis-install-dir.ts"),
      "utf8"
    );
    expect(maker).toContain('executableName: "AutoTaskStudio"');
    expect(maker).toContain("allowToChangeInstallationDirectory: false");
    expect(maker).toContain('WINDOWS_INSTALL_DIR = "D:\\\\Programs\\\\SMC\\\\AutoTask"');
  });
});
