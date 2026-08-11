---
name: replace-mock-api
description: 将 AutoTask Studio Mock 数据替换为真实 API。在对接 nodeskclaw-backend 或本地 FastAPI 时使用。
---

# Replace Mock API

Mock 替换真实 API 的标准流程。核心原则：**组件不变，只改 services 层**。

## 前置阅读

1. `docs/DATA_FLOW.md` — 数据流与 Query Key 约定
2. `.cursor/rules/api-data.mdc`

## 步骤

### 1. 创建 API Service

```
src/services/<domain>-api.ts
```

```typescript
const BASE_URL = 'http://localhost:8000/api';

export const taskApi = {
  getTasks: async (): Promise<AutomationTask[]> => {
    const res = await fetch(`${BASE_URL}/tasks`);
    if (!res.ok) throw new Error('Failed to fetch tasks');
    return res.json();
  },

  getTaskById: async (id: string): Promise<AutomationTask | undefined> => {
    const res = await fetch(`${BASE_URL}/tasks/${id}`);
    if (res.status === 404) return undefined;
    if (!res.ok) throw new Error('Failed to fetch task');
    return res.json();
  },
};
```

### 2. 创建切换入口（可选）

```typescript
// src/services/index.ts
import { mockApi } from './mock-api';
import { taskApi } from './task-api';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export const api = USE_MOCK ? mockApi : { ...mockApi, ...taskApi };
```

### 3. 替换 Feature 中的引用

```typescript
// 之前
import { mockApi } from '@/services/mock-api';
queryFn: mockApi.getTasks

// 之后
import { taskApi } from '@/services/task-api';
queryFn: taskApi.getTasks
```

### 4. 检查清单

- [ ] Query Key 未改变
- [ ] 返回类型与 `src/types/` 一致
- [ ] Loading 状态正常（useQuery isLoading）
- [ ] Error 状态有处理
- [ ] Empty 状态有处理（数据为空数组时）
- [ ] Mutation 后 invalidateQueries 正确
- [ ] 移除 Feature 层对 Zustand store 的依赖（如已迁移到后端）

### 5. 逐步替换

按模块逐个替换，不要一次替换所有 mock：

1. settings（最简单）
2. dashboard
3. tasks
4. workflows / runs / artifacts
5. srm-portals

## 禁止

- 修改 Feature 组件的 UI 结构
- 在组件中直接 fetch
- 删除 mock-api.ts（保留作为开发 fallback）

## 输出

列出替换的 API 方法、新增 service 文件、受影响的 Feature 文件。
