# AutoTask Context

> Agent 快速入口。详细说明见 [docs/CURSOR_CONTEXT.md](../docs/CURSOR_CONTEXT.md)。

## 当前阶段

Phase 1: Electron Mock UI

## 架构入口

```
src/
├── main.ts / preload.ts     Main + Preload
├── ipc/                     oRPC 路由（Native 能力）
├── actions/                 IPC 封装（Feature 调用此层）
├── routes/                  文件路由（薄层）
├── features/                业务模块
├── services/mock-api.ts     数据访问层
├── stores/                  Zustand
└── types/                   领域类型
```

## 业务模块

| 模块 | 路径 |
|------|------|
| Dashboard | `src/features/dashboard` |
| Tasks | `src/features/tasks` |
| Workflows | `src/features/workflows` |
| SRM | `src/features/srm-portals` |
| Runs | `src/features/runs` |
| Artifacts | `src/features/artifacts` |
| Web Workspace | `src/features/web-workspace` |

## 不要修改

- `components/ui/` — shadcn 基础组件
- `ipc/manager.ts`, `ipc/handler.ts` — IPC 引导
- `routes/__root.tsx` — 路由根
- `routeTree.gen.ts` — 自动生成

## 工作流

```
读 CURSOR_CONTEXT.md → 读 CODEBASE.md → 定位 feature → 遵守 rules → 最小修改
```

## 开发方向

```
Mock JSON → Local API → nodeskclaw-task → RPA Worker
```
