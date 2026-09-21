import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { MakerBase, type MakerOptions } from "@electron-forge/maker-base";
import type { ForgePlatform } from "@electron-forge/shared-types";

/** Default install directory for the Windows installer on the user's machine. */
export const WINDOWS_INSTALL_DIR = "D:\\Programs\\SMC\\AutoTask";

export class MakerNsisInstallDir extends MakerBase<Record<string, never>> {
  name = "nsis";
  defaultPlatforms: ForgePlatform[] = ["win32"];

  isSupportedOnCurrentPlatform(): boolean {
    return true;
  }

  async make({ dir, makeDir, targetArch }: MakerOptions): Promise<string[]> {
    const { buildForge } = await import("electron-builder");
    const outDir = path.resolve(makeDir, "nsis", targetArch);
    await this.ensureDirectory(outDir);

    const updateUrl =
      process.env.AUTOTASK_UPDATE_URL ??
      "https://release.superic.com/autotask/stable/";
    const resourcesDir = path.join(dir, "resources");
    await mkdir(resourcesDir, { recursive: true });
    await writeFile(
      path.join(resourcesDir, "app-update.yml"),
      `provider: generic\nurl: ${updateUrl}\nupdaterCacheDirName: AutoTask-updater\n`,
      "utf8"
    );

    return buildForge(
      { dir },
      {
        win: [`nsis:${targetArch}`],
        config: {
          appId: "com.smc.autotask",
          productName: "AutoTask",
          executableName: "AutoTaskStudio",
          // 在线更新：generic 静态源。地址打包时烧进 app-update.yml 并生成 latest.yml。
          // 可用 AUTOTASK_UPDATE_URL 覆盖（例如指向测试目录）。
          publish: {
            provider: "generic",
            url:
              process.env.AUTOTASK_UPDATE_URL ??
              "https://release.superic.com/autotask/stable/",
            channel: "latest",
          },
          forceCodeSigning: false,
          directories: {
            output: outDir,
          },
          nsis: {
            oneClick: false,
            perMachine: true,
            // 为 true 时，electron-builder 会在路径里再拼一层 APP_FILENAME（AutoTaskStudio）。
            allowToChangeInstallationDirectory: false,
            include: path.resolve(
              import.meta.dirname,
              "../installer/install-dir.nsh"
            ),
            artifactName: `AutoTask-Studio-\${version}-setup.\${ext}`,
            shortcutName: "AutoTask",
            createDesktopShortcut: true,
            createStartMenuShortcut: true,
          },
        },
      }
    );
  }
}
