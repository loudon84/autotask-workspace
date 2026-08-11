# AutoTask Studio 数据流

## 1. 总体数据流（当前 Mock 阶段）

```
┌──────────────┐     useQuery / useMutation     ┌──────────────┐
│   Feature    │ ─────────────────────────────► │  mock-api.ts │
│  Component   │ ◄───────────────────────────── │   (service)  │
└──────────────┘         Promise<T>              └──────┬───────┘
                                                        │
                              ┌─────────────────────────┼─────────────────┐
                              ▼                         ▼                 ▼
                        mock/*.json              Zustand stores      delay 模拟
```

**原则：** Component 不直接读 JSON，不直接操作 Store；一切经 `mockApi` 方法。

---

## 2. 典型读取流程

以任务列表为例：

```
routes/tasks/index.tsx
  → features/tasks/tasks-list.tsx
      → useQuery({ queryKey: ['tasks'], queryFn: mockApi.getTasks })
          → mockApi.getTasks()
              → mergeTasks(JSON, taskStore.addedTasks, taskStore.overrides)
              → delay(result)  // 模拟网络延迟
      → 渲染 DataTable
```

**Query Key 约定：**

| Key | 数据 |
|-----|------|
| `['dashboard']` | 工作台统计 |
| `['tasks']` | 任务列表 |
| `['tasks', taskId]` | 单个任务 |
| `['workflows']` | 流程模板 |
| `['workflows', id]` | 单个模板 |
| `['runs']` | 运行记录 |
| `['runs', runId]` | 单个运行 |
| `['srm-portals']` | SRM 门户 |
| `['artifacts']` | Artifact 列表 |
| `['workers']` | Worker 状态 |
| `['settings']` | 应用设置 |
| `['human-actions']` | 人工动作 |

---

## 3. 写入流程

以创建任务为例：

```
task-new.tsx
  → useMutation({ mutationFn: mockApi.createTask })
      → mockApi.createTask(data)
          → useTaskStore.getState().addTask(newTask)
          → delay(newTask)
  → onSuccess → queryClient.invalidateQueries(['tasks'])
```

以更新任务状态为例：

```
task-actions.tsx
  → mockApi.updateTaskStatus(id, status)
      → useTaskStore.getState().updateTaskStatus(id, status)
  → invalidateQueries(['tasks'], ['tasks', id])
```

---

## 4. Zustand Store 角色

Mock 阶段 Store 用于**模拟服务端持久化**：

| Store | 写入时机 | 读取时机 |
|-------|---------|---------|
| `task-store` | createTask / updateTask / updateTaskStatus | getTasks / getTaskById |
| `settings-store` | updateSettings | getSettings / getDelay |
| `human-action-store` | markHumanOpened / confirmHumanAction | getHumanActions |

Store 只在 `services/mock-api.ts` 内部使用，Feature 层不直接 import Store。

---

## 5. IPC 数据流

Native 能力不走 TanStack Query，走 actions 层：

```
Feature / Hook
  → actions/theme.ts (或其他 action)
      → ipc.client.theme.setThemeMode(mode)
          → MessagePort oRPC
              → ipc/theme/handlers.ts
                  → nativeTheme / BrowserWindow API
```

Web 工作区 Tab 更新是**推送式**：

```
Main: workspace-manager.ts
  → mainWindow.webContents.send(WEB_WORKSPACE_TAB_UPDATED, tab)
      → preload.ts 转发 postMessage
          → hooks/use-web-tab-updates.ts
              → Feature 组件更新 Tab UI
```

---

## 6. 全局搜索数据流

```
components/layout/global-search.tsx
  → mockApi.search(query)
      → 并行过滤 tasks / workflows / portals / runs
      → 返回 { tasks, workflows, portals, runs }
```

---

## 7. 人工处理流程

```
任务详情页 (WAITING_HUMAN 状态)
  → mockApi.markHumanOpened({ taskId, humanActionId })
      → human-action-store: status → OPENED
      → task-store: status → HUMAN_OPERATING
      → 打开 Web 工作区 Tab (IPC: webWorkspace.openHumanTask)
  → 用户操作完成后
  → mockApi.confirmHumanAction({ taskId, humanActionId, note })
      → task-store: status → SUCCESS_MANUAL
      → human-action-store: status → CONFIRMED
      → audit log 追加
```

---

## 8. 后续 API 替换策略

替换 Mock 为真实 API 时：

```
// 之前
import { mockApi } from '@/services/mock-api';
useQuery({ queryFn: () => mockApi.getTasks() })

// 之后
import { taskApi } from '@/services/task-api';
useQuery({ queryFn: () => taskApi.getTasks() })
```

**不变：** Feature 组件、Query Key、Loading/Error/Empty 状态处理。

**新增：** `src/services/task-api.ts` 等，内部调用 HTTP/WebSocket。

**Store 角色变化：** Mock 写入逻辑迁移到后端，Zustand 仅保留纯 UI 状态。
