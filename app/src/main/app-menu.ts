import { type BrowserWindow, Menu, app, shell } from "electron";
import { inDevelopment } from "@/constants";

export function setupApplicationMenu(
  getMainWindow: () => BrowserWindow | null | undefined
): void {
  const isMac = process.platform === "darwin";

  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: "about" as const },
              { type: "separator" as const },
              { role: "services" as const },
              { type: "separator" as const },
              { role: "hide" as const },
              { role: "hideOthers" as const },
              { role: "unhide" as const },
              { type: "separator" as const },
              { role: "quit" as const },
            ],
          },
        ]
      : []),
    {
      label: "文件",
      submenu: [
        isMac
          ? { role: "close" as const, label: "关闭窗口" }
          : { role: "quit" as const, label: "退出" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { role: "undo" as const, label: "撤销" },
        { role: "redo" as const, label: "重做" },
        { type: "separator" as const },
        { role: "cut" as const, label: "剪切" },
        { role: "copy" as const, label: "复制" },
        { role: "paste" as const, label: "粘贴" },
        { role: "selectAll" as const, label: "全选" },
      ],
    },
    {
      label: "视图",
      submenu: [
        {
          label: "重新加载",
          accelerator: "CmdOrCtrl+R",
          click: () => getMainWindow()?.webContents.reload(),
        },
        ...(inDevelopment
          ? [
              {
                label: "开发者工具",
                accelerator: isMac ? "Alt+Command+I" : "Ctrl+Shift+I",
                click: () => getMainWindow()?.webContents.toggleDevTools(),
              } satisfies Electron.MenuItemConstructorOptions,
            ]
          : []),
        { type: "separator" as const },
        { role: "resetZoom" as const, label: "重置缩放" },
        { role: "zoomIn" as const, label: "放大" },
        { role: "zoomOut" as const, label: "缩小" },
        { type: "separator" as const },
        { role: "togglefullscreen" as const, label: "全屏" },
      ],
    },
    {
      label: "窗口",
      submenu: [
        { role: "minimize" as const, label: "最小化" },
        ...(isMac
          ? [{ type: "separator" as const }, { role: "front" as const }]
          : [{ role: "close" as const, label: "关闭" }]),
      ],
    },
    {
      label: "帮助",
      submenu: [
        {
          label: "了解更多",
          click: async () => {
            await shell.openExternal("https://github.com/LuanRoger/electron-shadcn");
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
