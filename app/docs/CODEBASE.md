# AutoTask Studio Codebase Guide

> 基于仓库实际扫描生成。Agent 修改代码前请先读本文，再定位目标模块。

## 1. 项目定位

AutoTask Studio 是基于 Electron 的 **SRM 自动化桌面工作台**（`SMC-Copilot`）。

**核心职责：**

- 用户工作台（Dashboard）
- 自动化任务管理（Tasks）
- 流程模板管理（Workflows）
- 客户 SRM Portal 配置
- RPA 运行状态展示（Runs）
- Artifact / 日志展示
- Web 工作区（内嵌浏览器，WebContentsView）

**当前阶段：** Phase 1 — Electron Mock UI（数据来自 `mock-api.ts` + JSON）

**后续扩展：**

```
Desktop Client
  → Local API (nodeskclaw-backend)
  → Task Service (nodeskclaw-task)
  → Playwright RPA Worker
```

---

## 2. 技术栈

| 层级 | 技术 | 职责 |
|------|------|------|
| Desktop Runtime | Electron 42 + Forge + Vite 8 | 窗口、生命周期、Native 能力 |
| IPC | oRPC + MessagePort | Main ↔ Renderer 类型安全 RPC |
| Renderer | React 19 + TypeScript 6 | 页面渲染、用户交互 |
| 路由 | TanStack Router（文件路由） | 页面导航 |
| 服务端状态 | TanStack Query | API 数据缓存 |
| 本地 UI 状态 | Zustand | task/settings/human-action 等 |
| UI | shadcn/ui + Tailwind 4 | 基础组件、Layout |
| 校验 | Zod 4 | IPC input schema |
| 测试 | Vitest + Playwright | 单元 / E2E |
| 格式化 | Ultracite + Biome | lint / format |

---

## 3. 目录地图

```
autotask-studio/
├── src/
│   ├── main.ts                 # Electron Main 入口
│   ├── preload.ts              # IPC 桥（MessagePort + 事件转发）
│   ├── renderer.ts             # Renderer 入口
│   ├── app.tsx                 # React 根（QueryClient + Router）
│   │
│   ├── ipc/                    # Main 进程 oRPC 路由
│   │   ├── router.ts           # 聚合所有 IPC 模块
│   │   ├── handler.ts          # RPCHandler 实例
│   │   ├── manager.ts          # Renderer 侧 IPC 客户端
│   │   ├── context.ts          # MainWindow 上下文
│   │   ├── app/                # 应用信息
│   │   ├── theme/              # 主题切换
│   │   ├── window/             # 窗口控制
│   │   ├── shell/              # 外部链接
│   │   └── web-workspace/      # WebContentsView 工作区
│   │
│   ├── actions/                # Renderer 调用 IPC 的封装层
│   │   ├── app.ts
│   │   ├── theme.ts
│   │   ├── window.ts
│   │   ├── shell.ts
│   │   └── language.ts
│   │
│   ├── routes/                 # TanStack Router 文件路由（薄层）
│   │   ├── __root.tsx
│   │   ├── dashboard.tsx
│   │   ├── tasks/
│   │   ├── workflows/
│   │   ├── srm-portals/
│   │   ├── runs/
│   │   ├── artifacts.tsx
│   │   ├── settings.tsx
│   │   ├── components.tsx
│   │   └── web-workspace/
│   │
│   ├── features/               # 业务模块（页面逻辑）
│   │   ├── dashboard/
│   │   ├── tasks/
│   │   ├── workflows/
│   │   ├── srm-portals/
│   │   ├── runs/
│   │   ├── artifacts/
│   │   ├── components/
│   │   ├── settings/
│   │   └── web-workspace/
│   │
│   ├── components/
│   │   ├── ui/                 # shadcn 基础组件（勿改）
│   │   ├── layout/             # AppShell、Sidebar、Header
│   │   ├── business/           # 跨模块业务组件
│   │   └── common/             # 通用 UI（Table、EmptyState 等）
│   │
│   ├── services/
│   │   └── mock-api.ts         # 当前唯一数据访问层
│   │
│   ├── stores/                 # Zustand 本地状态
│   │   ├── task-store.ts
│   │   ├── settings-store.ts
│   │   └── human-action-store.ts
│   │
│   ├── types/                  # 领域类型定义
│   ├── mock/                   # Mock JSON 数据
│   ├── hooks/                  # 通用 hooks
│   ├── layouts/                # 根布局
│   ├── localization/           # i18n
│   ├── constants/              # 常量（IPC_CHANNELS 等）
│   ├── utils/                  # 工具函数
│   └── tests/                  # 单元 + E2E 测试
│
├── docs/                       # 项目文档（本目录）
├── .cursor/
│   ├── rules/                  # Agent 约束规则
│   ├── skills/                 # 常用开发流程
│   └── CURSOR_CONTEXT.md       # Agent 快速入口
├── prd/                        # 产品需求文档
└── forge.config.ts             # Electron Forge 配置
```

---

## 4. 路由 ↔ Feature 映射

| 路由 | Feature 入口 | 说明 |
|------|-------------|------|
| `/dashboard` | `features/dashboard/index.tsx` | 工作台 |
| `/tasks` | `features/tasks/tasks-list.tsx` | 任务列表 |
| `/tasks/new` | `features/tasks/task-new.tsx` | 新建任务 |
| `/tasks/$taskId` | `features/tasks/task-detail.tsx` | 任务详情 |
| `/workflows` | `features/workflows/workflows-list.tsx` | 流程模板列表 |
| `/workflows/$workflowId` | `features/workflows/workflow-detail.tsx` | 模板详情 |
| `/srm-portals` | `features/srm-portals/srm-portals-list.tsx` | SRM 门户列表 |
| `/srm-portals/$portalId` | `features/srm-portals/srm-portal-detail.tsx` | 门户配置 |
| `/runs` | `features/runs/runs-list.tsx` | 运行监控 |
| `/runs/$runId` | `features/runs/run-detail.tsx` | 运行详情 |
| `/artifacts` | `features/artifacts/index.tsx` | 任务记录 |
| `/components` | `features/components/index.tsx` | RPA 组件库 |
| `/settings` | `features/settings/index.tsx` | 系统设置 |
| `/web-workspace` | `features/web-workspace/web-workspace-page.tsx` | Web 工作区 |

导航配置：`src/components/layout/data/sidebar-data.ts`

---

## 5. 数据访问

当前所有业务数据经 `src/services/mock-api.ts` 访问：

```
Component → useQuery/useMutation → mockApi.xxx() → mock/*.json + Zustand stores
```

替换真实 API 时**只改 services 层**，组件保持不变。

---

## 6. IPC 概览

Renderer 通过 `src/ipc/manager.ts` 创建 oRPC 客户端，经 MessagePort 与 Main 通信。

```
Renderer: ipc.client.<module>.<method>()
    ↓ MessagePort
Main: src/ipc/router.ts → src/ipc/<module>/handlers.ts
```

Renderer 侧封装在 `src/actions/`，Feature 应调用 actions 而非直接 `ipc.client`。

详见 [IPC_CONTRACT.md](./IPC_CONTRACT.md)。

---

## 7. 关键约束

**禁止：**

- Renderer 直接使用 `fs`、`path`、`electron`、`ipcRenderer`
- Feature 直接 import 其他 Feature 的内部文件
- 页面组件直接 import JSON mock 数据
- 修改 `components/ui/` 下的 shadcn 生成组件

**必须：**

- Native 能力 → Main IPC → Preload → actions → Feature
- 数据访问 → services 层
- 新页面 → routes（薄层）+ features（逻辑）

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构分层与运行时 |
| [MODULES.md](./MODULES.md) | 各模块职责与文件清单 |
| [DATA_FLOW.md](./DATA_FLOW.md) | 数据流与状态管理 |
| [IPC_CONTRACT.md](./IPC_CONTRACT.md) | IPC 接口契约 |
| [CURSOR_CONTEXT.md](./CURSOR_CONTEXT.md) | Agent 工作入口 |
| [autotask-studio.md](./autotask-studio.md) | 产品架构总览（远期规划） |
