---
name: refactor-module
description: 重构 AutoTask Studio 单个业务模块。在需要重组 feature 内部结构、拆分组件或调整依赖时使用。
---

# Refactor Module

模块重构的标准流程。禁止一次重构整个 `src/`。

## 前置阅读

1. `docs/MODULES.md` — 目标模块职责
2. `docs/CODEBASE.md` — 目录地图
3. `.cursor/rules/architecture.mdc`

## 步骤

### 1. 生成模块地图

在动手前，先分析并记录：

```markdown
# MODULE_MAP: <module-name>

## 当前文件
- features/<module>/xxx.tsx — 职责
- routes/<module>/xxx.tsx — 路由
- components/business/xxx.tsx — 共享组件
- services/mock-api.ts — 相关 API 方法
- types/xxx.ts — 类型

## 依赖关系
- 依赖 mockApi.getXxx
- 依赖 components/business/StatusBadge
- 被 routes/<module>/ 引用

## 修改范围
- [ ] 仅 features/<module>/ 内部
- [ ] 需要调整 components/business/
- [ ] 需要调整 services/
- [ ] 需要调整 types/

## 接口兼容
- 导出函数签名不变
- Query Key 不变
- 路由路径不变
```

### 2. 执行重构

规则：

1. **保持接口兼容** — 导出的组件名、props、service 方法签名不变
2. **不跨模块移动大量代码** — 共享逻辑提取到 `components/business/` 或 `services/`
3. **先文档后代码** — 先完成 MODULE_MAP，再修改
4. **小步提交** — 每次只重构一个模块

### 3. 重构模式

**拆分大组件：**

```
features/tasks/task-detail.tsx (过大)
  → features/tasks/task-detail.tsx (编排)
  → features/tasks/components/task-info.tsx
  → features/tasks/components/task-runs.tsx
  → features/tasks/components/task-actions-panel.tsx
```

**提取共享逻辑：**

```
features/A/internal-helper.ts + features/B/internal-helper.ts (重复)
  → components/business/shared-helper.tsx
  或 hooks/use-shared-logic.ts
```

**提取 service：**

```
mock-api.ts 中某模块方法过多
  → services/task-api.ts（从 mock-api 拆出）
  → mock-api.ts re-export 保持兼容
```

### 4. 验证

- [ ] 路由仍正常工作
- [ ] 所有 import 路径已更新
- [ ] 无跨 feature 内部 import
- [ ] 测试通过（`npm run test`）
- [ ] 无 TypeScript 错误

## 禁止

- 一次重构整个 `src/`
- 修改 `components/ui/`
- 修改 IPC 引导逻辑
- 改变路由路径或 Query Key
- 删除架构约束文档

## 输出

完成后提供 MODULE_MAP 和修改文件清单。
