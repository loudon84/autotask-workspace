---
name: add-feature
description: 新增 AutoTask Studio 业务模块。在需要创建新 feature（如新的管理页面、业务领域）时使用。
---

# Add Feature

新增业务模块的标准流程。

## 前置阅读

1. `docs/CODEBASE.md` — 确认模块是否已存在
2. `docs/MODULES.md` — 了解现有模块结构
3. `.cursor/rules/react-feature.mdc` — Feature 规范

## 步骤

### 1. 创建 Feature 目录

```
src/features/<name>/
├── <name>-list.tsx       # 列表页入口
├── <name>-detail.tsx     # 详情页（如需要）
├── components/           # 模块私有组件
├── hooks/                # 模块私有 hooks
└── types.ts              # 模块私有类型（优先用 src/types/）
```

### 2. 添加类型

在 `src/types/<domain>.ts` 定义领域类型。

### 3. 添加 Mock 数据

在 `src/mock/<name>.json` 添加 JSON，并在 `src/services/mock-api.ts` 注册方法。

### 4. 注册路由

```
src/routes/<name>/index.tsx          # 列表
src/routes/<name>/$<name>Id.tsx       # 详情（如需要）
```

路由文件只做薄层 import：

```typescript
import { createFileRoute } from '@tanstack/react-router';
import { MyListPage } from '@/features/<name>/<name>-list';

export const Route = createFileRoute('/<name>/')({
  component: MyListPage,
});
```

### 5. 注册导航

编辑 `src/components/layout/data/sidebar-data.ts`：

- 添加 sidebar item
- 添加 `routeTitles` 条目

### 6. 添加测试

至少一个 service 或组件测试。

## 检查清单

- [ ] Feature 不直接 import JSON 或 IPC
- [ ] 数据经 `mockApi` / service 访问
- [ ] 路由是薄层
- [ ] Sidebar 已注册
- [ ] 使用已有 UI 组件（DataTable、PageHeader、EmptyState）
- [ ] 未修改 `components/ui/`

## 输出

完成后列出新增/修改的文件清单。
