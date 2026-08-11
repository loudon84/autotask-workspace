# AutoTask Studio — Agent 工作入口

> 每次新任务先读本文，再按需阅读对应模块文档。避免全量扫描 `src/`。

## 当前阶段

**Phase 1：Electron Mock UI**

- 业务数据来自 `src/services/mock-api.ts` + `src/mock/*.json`
- Web 工作区已接入 WebContentsView（v0.4）
- 尚未对接后端 API / RPA Worker

## 架构入口

```
docs/CODEBASE.md      ← 目录地图（首选）
docs/MODULES.md       ← 模块职责
docs/ARCHITECTURE.md  ← 分层架构
docs/DATA_FLOW.md     ← 数据流
docs/IPC_CONTRACT.md  ← IPC 接口
```

## 业务模块速查

| 模块 | 路径 |
|------|------|
| Dashboard | `src/features/dashboard/` |
| Tasks | `src/features/tasks/` |
| Workflows | `src/features/workflows/` |
| SRM Portals | `src/features/srm-portals/` |
| Runs | `src/features/runs/` |
| Artifacts | `src/features/artifacts/` |
| RPA Components | `src/features/components/` |
| Settings | `src/features/settings/` |
| Web Workspace | `src/features/web-workspace/` |

路由（薄层）：`src/routes/`
导航配置：`src/components/layout/data/sidebar-data.ts`

## 分层速查

| 层 | 路径 | 说明 |
|----|------|------|
| Main | `src/main.ts`, `src/ipc/` | Electron 主进程 + oRPC |
| Preload | `src/preload.ts` | MessagePort 桥 |
| Actions | `src/actions/` | Renderer IPC 封装 |
| Services | `src/services/mock-api.ts` | 数据访问 |
| Stores | `src/stores/` | Zustand（仅 mock 阶段写入） |
| Types | `src/types/` | 领域类型 |

## 不要修改

- `src/components/ui/` — shadcn 生成组件
- `src/ipc/manager.ts` — IPC 客户端引导
- `src/ipc/handler.ts` — oRPC handler 引导
- `src/routes/__root.tsx` — 路由根布局
- `src/routeTree.gen.ts` — 自动生成

## 修改原则

1. 先读 `docs/CODEBASE.md` 定位目标模块
2. 只扫描目标 feature / ipc 目录
3. 遵守 `.cursor/rules/` 约束
4. 最小范围修改，禁止全局重构
5. 新功能优先加 feature，不改公共组件

## 当前开发方向

```
Mock JSON → Local API → nodeskclaw-task → RPA Worker
```

替换 API 时只改 `services/` 层，组件保持不变。

## 常用 Skills

| Skill | 用途 |
|-------|------|
| `.cursor/skills/add-feature/` | 新增业务模块 |
| `.cursor/skills/add-page/` | 新增页面 |
| `.cursor/skills/add-ipc/` | 新增 Native 能力 |
| `.cursor/skills/replace-mock-api/` | Mock 替换真实 API |
| `.cursor/skills/refactor-module/` | 模块重构 |
