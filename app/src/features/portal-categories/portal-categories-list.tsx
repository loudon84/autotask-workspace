import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { usePortalCategories } from "@/features/portal-categories/api/use-portal-categories";
import type { CategorySummary } from "@/types/category-document";

export function PortalCategoriesListPage() {
  const { data: categories = [], isLoading } = usePortalCategories();

  const columns: ColumnDef<CategorySummary>[] = useMemo(
    () => [
      {
        accessorKey: "label",
        header: "分类",
        cell: ({ row }) => (
          <Link
            className="font-medium text-primary hover:underline"
            params={{ category: row.original.code }}
            to="/portal-categories/$category"
          >
            {row.original.label}
          </Link>
        ),
      },
      { accessorKey: "code", header: "代码" },
      {
        accessorKey: "documentCount",
        header: "文档数",
      },
    ],
    []
  );

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader
        description="文档按客户分类维护，不挂在单个门户上。天地伟业多条门户共用一份手册。"
        title="门户分类"
      />
      {categories.length === 0 ? (
        <EmptyState title="没有分类" />
      ) : (
        <DataTable columns={columns} data={categories} />
      )}
    </div>
  );
}
