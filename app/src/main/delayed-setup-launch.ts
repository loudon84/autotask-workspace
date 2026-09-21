/** NSIS 在线升级：不静默，安装窗口显示进度；不选目录。 */
export const NSIS_UPDATE_ARGS = ["--updated", "--force-run"] as const;

/** 独立 cmd：覆盖升级并在完成后拉起新版本。 */
// @lat: [[client#Online Updates]]
export function nsisUpdateStartCommand(setupPath: string): string {
  return `start "" "${setupPath}" ${NSIS_UPDATE_ARGS.join(" ")}`;
}
