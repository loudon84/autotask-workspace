---
name: add-ipc
description: 新增 AutoTask Studio Electron Native 能力（oRPC IPC）。在需要 Main 进程能力（文件系统、系统 API、Native 窗口等）时使用。
---

# Add IPC

新增 Electron Native 能力的标准流程。

## 前置阅读

1. `docs/IPC_CONTRACT.md` — 现有 IPC 契约
2. `.cursor/rules/electron.mdc`

## 步骤

### 1. 创建 IPC 模块

```
src/ipc/<feature>/
├── handlers.ts     # oRPC handler
├── schemas.ts      # Zod input schema（有参数时）
└── index.ts        # 导出模块对象
```

**handlers.ts 模板：**

```typescript
import { os } from '@orpc/server';
import { myInputSchema } from './schemas';

export const myMethod = os
  .input(myInputSchema)
  .handler(({ input }) => {
    // Main 进程逻辑
    return { success: true };
  });
```

**index.ts 模板：**

```typescript
import { myMethod } from './handlers';

export const myFeature = {
  myMethod,
};
```

### 2. 注册到 Router

```typescript
// src/ipc/router.ts
import { myFeature } from './<feature>';

export const router = {
  // ...existing
  myFeature,
};
```

### 3. 创建 Renderer 封装

```typescript
// src/actions/<feature>.ts
import { ipc } from '@/ipc/manager';

export async function myAction(input: MyInput) {
  return ipc.client.myFeature.myMethod(input);
}
```

### 4. Feature 层调用

```typescript
// features/xxx/xxx.tsx
import { myAction } from '@/actions/<feature>';
await myAction({ ... });
```

### 5. 验证

- Renderer 可通过 action 调用
- Feature 不直接使用 `ipc.client`
- TypeScript 类型正确推导

## 禁止

- Renderer 使用 `ipcRenderer`、`fs`、`path`
- 跳过 `actions/` 层直接在 Feature 调用 `ipc.client`
- 修改 `ipc/manager.ts` 引导逻辑

## 参考实现

- 简单模块：`ipc/app/`, `ipc/theme/`
- 复杂模块：`ipc/web-workspace/`

## 输出

完成后列出新增/修改的文件清单，并说明 Renderer 调用方式。
