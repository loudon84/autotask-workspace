---
name: add-page
description: 在 AutoTask Studio 中新增页面（路由 + 导航）。在已有 feature 下加子页面或新建简单页面时使用。
---

# Add Page

新增页面的标准流程。

## 前置阅读

1. `docs/CODEBASE.md` — 路由 ↔ Feature 映射
2. `.cursor/rules/react-feature.mdc`

## 步骤

### 1. 确定页面归属

- 属于已有 feature → 在 `features/<module>/` 添加组件
- 全新业务 → 使用 `add-feature` skill

### 2. 创建页面组件

```typescript
// features/<module>/<page-name>.tsx
export function MyPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['my-data'],
    queryFn: mockApi.getMyData,
  });

  if (isLoading) return <MockLoading />;
  if (!data?.length) return <EmptyState title="暂无数据" />;

  return (
    <>
      <PageHeader title="页面标题" />
      {/* 页面内容 */}
    </>
  );
}
```

### 3. 注册路由

```
src/routes/<path>.tsx              # 简单路由
src/routes/<module>/<page>.tsx     # 嵌套路由
```

### 4. 注册导航

`src/components/layout/data/sidebar-data.ts`：

- `navGroups` 添加 item
- `routeTitles` 添加标题
- `getPageTitle()` 添加动态标题（如有 `$param` 路由）

### 5. 检查

- [ ] 使用 `AppShell` 布局（通过 `__root.tsx` 自动包裹）
- [ ] 有 Loading 状态（`MockLoading`）
- [ ] 有 Empty 状态（`EmptyState`）
- [ ] 复用 `DataTable` / `PageHeader` / `FilterBar`
- [ ] 数据经 service 访问

## 输出

完成后列出新增/修改的文件清单。
