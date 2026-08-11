# AutoTask Studio 架构说明

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Desktop                      │
│                                                          │
│  ┌─────────────┐   MessagePort/oRPC   ┌──────────────┐  │
│  │  Renderer   │ ◄──────────────────► │  Main Process │  │
│  │  React App  │                      │  Node.js      │  │
│  └──────┬──────┘                      └───────┬───────┘  │
│         │                                     │          │
│         │                              WebContentsView   │
│         │                              (web-workspace)   │
└─────────┼─────────────────────────────────────┼──────────┘
          │                                     │
          │ mock-api (当前)                      │ 内嵌浏览器
          ▼                                     ▼
   mock/*.json + Zustand              客户 SRM Portal
          │
          │ 后续
          ▼
   nodeskclaw-backend (FastAPI)
          │
          ▼
   nodeskclaw-task + Playwright Worker
```

---

## 2. 进程分层

### Main Process (`src/main.ts`)

- 创建 `BrowserWindow`
- 注册 oRPC handler（`ipc/handler.ts`）
- 管理 WebContentsView 工作区（`ipc/web-workspace/`）
- 系统能力：主题、窗口控制、外部链接

### Preload (`src/preload.ts`)

- 转发 MessagePort 到 Main（`START_ORPC_SERVER`）
- 转发 Web 工作区 Tab 更新事件到 Renderer

### Renderer (`src/app.tsx` → routes → features)

- React 应用，Context Isolation 下无 Node 权限
- 通过 `ipc/manager.ts` 调用 Native 能力
- 通过 `services/mock-api.ts` 获取业务数据

---

## 3. IPC 架构（oRPC）

项目使用 [oRPC](https://orpc.unnoq.com) 替代传统 `ipcMain.handle`：

```
Renderer                          Main
────────                          ────
ipc/manager.ts                    ipc/handler.ts
  createORPCClient()                RPCHandler(router)
  MessageChannel port1  ◄────────►  MessageChannel port2
                                    ipc/router.ts
                                      ├── theme
                                      ├── window
                                      ├── app
                                      ├── shell
                                      └── webWorkspace
```

**初始化流程：**

1. Renderer `IPCManager` 创建 `MessageChannel`
2. 通过 `window.postMessage` 发送 serverPort 给 Preload
3. Preload 转发给 Main 的 `ipcMain.on(START_ORPC_SERVER)`
4. Main `rpcHandler.upgrade(serverPort)` 建立 RPC 连接

---

## 4. 前端分层

```
routes/          路由定义（createFileRoute，仅 import feature 组件）
    ↓
features/        业务页面逻辑（useQuery、表单、列表）
    ↓
components/      UI 组件
  ├── ui/        shadcn 基础组件
  ├── business/  跨模块业务组件（StatusBadge、TaskActions 等）
  ├── common/    通用组件（DataTable、PageHeader 等）
  └── layout/    应用骨架（AppShell、Sidebar）
    ↓
services/        数据访问层
actions/         IPC 封装层
stores/          Zustand 本地状态
types/           TypeScript 类型
```

---

## 5. 状态管理策略

| 类型 | 方案 | 示例 |
|------|------|------|
| 服务端/远程数据 | TanStack Query | 任务列表、Dashboard 统计 |
| 本地 UI 状态 | Zustand | mock 写入的任务覆盖、设置 |
| 主题/语言 | localStorage + IPC | theme、i18n |
| Web Tab 状态 | Main 进程 tab-store + IPC 事件 | web-workspace |

Query 默认配置（`app.tsx`）：`staleTime: 30s`, `retry: 1`

---

## 6. Web 工作区架构

Web 工作区是 v0.4 引入的核心 Native 能力，使用 Electron `WebContentsView`：

```
features/web-workspace/     UI（Tab 栏、地址栏、工具栏）
        ↓ actions
ipc/web-workspace/
  ├── handlers.ts           oRPC 方法定义
  ├── workspace-manager.ts  WebContentsView 生命周期
  ├── tab-store.ts          Tab 状态
  └── session-manager.ts    Session/Partition 管理
        ↓
Main Window 内嵌 WebContentsView
```

Tab 更新通过 `WEB_WORKSPACE_TAB_UPDATED` 事件从 Main 推送到 Renderer。

---

## 7. 构建与打包

- **开发：** `npm run start` → Electron Forge + Vite HMR
- **打包：** Electron Forge makers（zip/deb/rpm/squirrel）
- **Vite 配置：** `vite.main.config.mts` / `vite.preload.config.mts` / renderer 内联
- **路径别名：** `@/` → `src/`

---

## 8. 演进路线

```
Phase 1 (当前)  Mock UI — mock-api.ts + JSON
Phase 2         Local API — services 层对接 FastAPI
Phase 3         Task Service — 真实任务调度
Phase 4         RPA Worker — Playwright 执行引擎
```

每阶段保持 Renderer 组件接口不变，仅替换 services 层和 IPC 扩展。
