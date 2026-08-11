# AutoTask Studio 模块职责

## Feature 模块

### dashboard — 工作台

**路径：** `src/features/dashboard/`

**职责：** 展示今日任务统计、Worker 状态、最近运行、异常任务。

**关键文件：**

| 文件 | 说明 |
|------|------|
| `index.tsx` | Dashboard 页面，useQuery 拉取 mockApi.getDashboard |

**依赖：** `mockApi.getDashboard`, `mockApi.getTasks`, `mockApi.getWorkers`

---

### tasks — 自动化任务

**路径：** `src/features/tasks/`

**职责：** 任务 CRUD、状态流转、人工处理入口。

| 文件 | 说明 |
|------|------|
| `tasks-list.tsx` | 任务列表页 |
| `task-detail.tsx` | 任务详情（步骤、运行记录、人工检查点） |
| `task-new.tsx` | 新建任务表单 |

**关联类型：** `src/types/automation-task.ts`, `src/types/human-action.ts`

**关联 Store：** `task-store.ts`, `human-action-store.ts`

**关联组件：** `components/business/task-actions.tsx`, `human-checkpoint-panel.tsx`

---

### workflows — 流程模板

**路径：** `src/features/workflows/`

**职责：** 流程模板列表与详情展示。

| 文件 | 说明 |
|------|------|
| `workflows-list.tsx` | 模板列表 |
| `workflow-detail.tsx` | 模板详情（步骤卡片） |

**Mock 数据：** `mock/workflow-templates.json`

---

### srm-portals — 客户 SRM 配置

**路径：** `src/features/srm-portals/`

**职责：** SRM Portal 列表、配置详情、登录状态展示。

| 文件 | 说明 |
|------|------|
| `srm-portals-list.tsx` | 门户列表 |
| `srm-portal-detail.tsx` | 门户详情与操作 |

**Mock 数据：** `mock/srm-portals.json`

**关联组件：** `components/business/srm-portal-card.tsx`, `portal-actions.tsx`, `login-state-badge.tsx`

---

### runs — RPA 运行监控

**路径：** `src/features/runs/`

**职责：** 运行记录列表与详情（步骤时间线、日志）。

| 文件 | 说明 |
|------|------|
| `runs-list.tsx` | 运行列表 |
| `run-detail.tsx` | 运行详情 |

**Mock 数据：** `mock/task-runs.json`

**关联组件：** `components/business/step-timeline.tsx`, `run-log-panel.tsx`

---

### artifacts — 任务记录

**路径：** `src/features/artifacts/`

**职责：** 截图、Trace、文件等 Artifact 展示。

**Mock 数据：** `mock/artifacts.json`

**关联组件：** `components/business/artifact-preview.tsx`

---

### components — RPA 组件库

**路径：** `src/features/components/`

**职责：** RPA 可复用组件目录展示。

**Mock 数据：** `mock/rpa-components.json`

---

### settings — 系统设置

**路径：** `src/features/settings/`

**职责：** Mock 延迟、主题等应用设置。

**关联 Store：** `settings-store.ts`

**Mock 数据：** `mock/settings.json`

---

### web-workspace — Web 工作区

**路径：** `src/features/web-workspace/`

**职责：** 内嵌浏览器 Tab 管理、地址栏、Portal/人工任务打开。

| 文件 | 说明 |
|------|------|
| `web-workspace-page.tsx` | 主页面 |
| `web-tab-bar.tsx` | Tab 栏 |
| `web-address-input.tsx` | 地址栏 |
| `web-toolbar.tsx` | 导航工具栏 |
| `web-empty-state.tsx` | 空状态 |

**IPC 模块：** `ipc/web-workspace/`

**Hook：** `hooks/use-web-tab-updates.ts`

---

## IPC 模块

| 模块 | 路径 | 职责 |
|------|------|------|
| app | `ipc/app/` | 平台信息、应用版本 |
| theme | `ipc/theme/` | 系统主题读取/切换 |
| window | `ipc/window/` | 最小化/最大化/关闭 |
| shell | `ipc/shell/` | 外部链接打开 |
| webWorkspace | `ipc/web-workspace/` | WebContentsView 全生命周期 |

IPC 聚合入口：`ipc/router.ts`

---

## 共享层

### components/business — 跨模块业务组件

| 组件 | 用途 |
|------|------|
| `status-badge.tsx` | 任务/运行状态标签 |
| `priority-badge.tsx` | 优先级标签 |
| `task-actions.tsx` | 任务操作按钮组 |
| `worker-status-card.tsx` | Worker 状态卡片 |
| `workflow-step-card.tsx` | 流程步骤卡片 |
| `step-timeline.tsx` | 步骤时间线 |
| `human-checkpoint-panel.tsx` | 人工检查点面板 |
| `artifact-preview.tsx` | Artifact 预览 |
| `run-log-panel.tsx` | 运行日志面板 |
| `srm-portal-card.tsx` | Portal 卡片 |
| `portal-actions.tsx` | Portal 操作 |
| `login-state-badge.tsx` | 登录状态 |
| `progress-cell.tsx` | 进度条单元格 |

### components/layout — 应用骨架

| 组件 | 用途 |
|------|------|
| `app-shell.tsx` | 主布局容器 |
| `app-sidebar.tsx` | 侧边栏 |
| `app-header.tsx` | 顶栏 |
| `page-layout.tsx` | 页面内容区 |
| `data/sidebar-data.ts` | 导航配置 |

### stores — Zustand

| Store | 用途 |
|-------|------|
| `task-store.ts` | Mock 阶段任务增删改覆盖 |
| `settings-store.ts` | 应用设置（mockDelayMs 等） |
| `human-action-store.ts` | 人工动作状态 |

### types — 领域类型

| 文件 | 领域 |
|------|------|
| `automation-task.ts` | 自动化任务 |
| `task-run.ts` | 运行记录 |
| `workflow.ts` | 流程模板 |
| `srm-portal.ts` | SRM 门户 |
| `artifact.ts` | 证据文件 |
| `worker.ts` | RPA Worker |
| `human-action.ts` | 人工动作 |
| `dashboard.ts` | 工作台数据 |
| `rpa-component.ts` | RPA 组件 |
| `audit-log.ts` | 审计日志 |
| `web-tab.ts` | Web Tab |
| `settings.ts` | 应用设置 |

---

## Feature 模块规范

新增业务模块应遵循：

```
features/<name>/
├── index.tsx          # 或 <name>-list.tsx 等入口
├── components/        # 模块私有组件（可选）
├── hooks/             # 模块私有 hooks（可选）
├── services/          # 模块私有 service（可选，优先用全局 services/）
└── types.ts           # 模块私有类型（可选，优先用全局 types/）
```

**禁止：**

- 跨 feature 直接 import 内部文件（应通过 `components/business` 或 `services` 共享）
- 页面直接访问 JSON 或 IPC
