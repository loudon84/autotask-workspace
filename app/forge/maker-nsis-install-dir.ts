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

    return buildForge(
      { dir },
      {
        win: [`nsis:${targetArch}`],
        config: {
          appId: "com.smc.autotask",
          productName: "AutoTask",
          publish: null,
          forceCodeSigning: false,
          directories: {
            output: outDir,
          },
          nsis: {
            oneClick: false,
            perMachine: true,
            allowToChangeInstallationDirectory: true,
            include: path.resolve(
              import.meta.dirname,
              "../installer/install-dir.nsh"
            ),
            artifactName: "AutoTask-Studio.exe",
            shortcutName: "AutoTask",
            createDesktopShortcut: true,
            createStartMenuShortcut: true,
          },
        },
      }
    );
  }
}
