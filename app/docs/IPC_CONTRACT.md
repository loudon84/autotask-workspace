# AutoTask Studio IPC 契约

## 1. 通信机制

项目使用 **oRPC + MessagePort**，非传统 Electron `ipcMain.handle`。

| 层 | 文件 | 职责 |
|----|------|------|
| Renderer 客户端 | `src/ipc/manager.ts` | 创建 MessageChannel，`ipc.client` |
| Renderer 封装 | `src/actions/*.ts` | Feature 调用入口 |
| Preload | `src/preload.ts` | 转发 MessagePort |
| Main Handler | `src/ipc/handler.ts` | RPCHandler 实例 |
| Main Router | `src/ipc/router.ts` | 模块聚合 |

**Legacy 事件通道（非 oRPC）：**

| Channel | 方向 | 用途 |
|---------|------|------|
| `start-orpc-server` | Renderer → Main | 建立 oRPC 连接 |
| `web-workspace-tab-updated` | Main → Renderer | Tab 状态推送 |

定义位置：`src/constants/index.ts` → `IPC_CHANNELS`

---

## 2. Router 模块清单

```typescript
// src/ipc/router.ts
export const router = {
  theme,        // 主题
  window,       // 窗口控制
  app,          // 应用信息
  shell,        // 外部链接
  webWorkspace, // Web 工作区
};
```

Renderer 调用方式：

```typescript
import { ipc } from '@/ipc/manager';
await ipc.client.theme.setThemeMode('dark');
await ipc.client.webWorkspace.openUrl({ url: '...' });
```

Feature 层应通过 `src/actions/` 调用，不直接使用 `ipc.client`。

---

## 3. app 模块

**路径：** `src/ipc/app/`

| 方法 | 输入 | 返回 | 说明 |
|------|------|------|------|
| `currentPlatfom` | — | `string` | 当前操作系统平台 |
| `appVersion` | — | `string` | 应用版本号 |

**Renderer 封装：** `src/actions/app.ts`

---

## 4. theme 模块

**路径：** `src/ipc/theme/`

| 方法 | 输入 | 返回 | 说明 |
|------|------|------|------|
| `getCurrentThemeMode` | — | `'light' \| 'dark' \| 'system'` | 获取当前主题 |
| `setThemeMode` | `ThemeMode` | `void` | 设置主题 |
| `toggleThemeMode` | — | `boolean` | 切换主题，返回是否 dark |

**Schema：** `src/ipc/theme/schemas.ts`

**Renderer 封装：** `src/actions/theme.ts`（同步 localStorage）

---

## 5. window 模块

**路径：** `src/ipc/window/`

| 方法 | 输入 | 返回 | 说明 |
|------|------|------|------|
| `minimizeWindow` | — | `void` | 最小化 |
| `maximizeWindow` | — | `void` | 最大化/还原 |
| `closeWindow` | — | `void` | 关闭窗口 |

**Renderer 封装：** `src/actions/window.ts`

---

## 6. shell 模块

**路径：** `src/ipc/shell/`

| 方法 | 输入 | 返回 | 说明 |
|------|------|------|------|
| `openExternalLink` | `{ url: string }` | `void` | 系统浏览器打开链接 |

**Schema：** `src/ipc/shell/schemas.ts`

**Renderer 封装：** `src/actions/shell.ts`

---

## 7. webWorkspace 模块

**路径：** `src/ipc/web-workspace/`

核心 Native 能力，管理 WebContentsView Tab。

| 方法 | 说明 |
|------|------|
| `initWorkspace` | 初始化工作区 |
| `openUrl` | 打开 URL（新 Tab） |
| `openPortal` | 打开 SRM Portal Tab |
| `openHumanTask` | 打开人工任务 Tab（带 session partition） |
| `closeTab` | 关闭 Tab |
| `activateTab` | 激活 Tab |
| `reload` | 刷新 |
| `goBack` / `goForward` | 导航 |
| `copyUrl` | 复制当前 URL |
| `openExternal` | 系统浏览器打开 |
| `listTabs` | 列出所有 Tab |
| `getActiveTab` | 获取当前 Tab |
| `setBounds` | 设置 WebContentsView 位置/大小 |
| `setVisibility` | 显示/隐藏 |
| `clearPortalSession` | 清除 Portal Session |
| `clearAllSessions` | 清除所有 Session |

**Schema：** `src/ipc/web-workspace/schemas.ts`

**核心实现：** `workspace-manager.ts`, `tab-store.ts`, `session-manager.ts`

**Tab 推送：** Main 通过 `WEB_WORKSPACE_TAB_UPDATED` 事件推送 Tab 变更。

---

## 8. 新增 IPC 流程

新增 Native 能力必须：

```
1. src/ipc/<feature>/
     ├── handlers.ts    # oRPC handler（os.input().handler()）
     ├── schemas.ts     # Zod input schema（如需）
     └── index.ts       # 导出模块对象

2. src/ipc/router.ts    # 注册到 router

3. src/actions/<feature>.ts  # Renderer 封装

4. Feature 层调用 actions，不直接 ipc.client
```

**禁止 Renderer 使用：**

- `window.require()`
- `ipcRenderer` 直接调用
- `fs` / `path` / Node API

---

## 9. IPC Context

`src/ipc/context.ts` 提供 MainWindow 上下文 middleware：

```typescript
ipcContext.mainWindowContext  // 需要 window 的 handler 使用
```

当前 web-workspace 部分 handler 通过 `webWorkspaceManager.setMainWindow()` 获取窗口引用。
