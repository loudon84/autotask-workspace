import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, Trash2, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { selectCategoryDocumentFiles } from "@/actions/shell";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import {
  useDeleteCategoryDocument,
  useUploadCategoryDocuments,
} from "@/features/portal-categories/api/use-category-document-mutations";
import { useCategoryDocuments } from "@/features/portal-categories/api/use-portal-categories";
import { portalCategoryLabel } from "@/features/srm-portals/portal-category";
import { autotaskApi } from "@/services/autotask-api";
import type { CategoryDocument } from "@/types/category-document";
import { formatBeijingDateTime } from "@/utils/date-time";

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function PortalCategoryDocumentsPage({
  category,
}: {
  category: string;
}) {
  const label = portalCategoryLabel(category);
  const { data: documents = [], isLoading } = useCategoryDocuments(category);
  const uploadMutation = useUploadCategoryDocuments(category);
  const deleteMutation = useDeleteCategoryDocument(category);
  const [pendingDelete, setPendingDelete] = useState<CategoryDocument | null>(
    null
  );

  const columns: ColumnDef<CategoryDocument>[] = useMemo(
    () => [
      { accessorKey: "originalFilename", header: "文件名" },
      {
        accessorKey: "byteSize",
        header: "大小",
        cell: ({ row }) => formatBytes(row.original.byteSize),
      },
      {
        accessorKey: "uploadedByName",
        header: "上传人",
        cell: ({ row }) => row.original.uploadedByName || "—",
      },
      {
        accessorKey: "createdAt",
        header: "上传时间",
        cell: ({ row }) => formatBeijingDateTime(row.original.createdAt),
      },
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => (
          <div className="flex flex-nowrap items-center gap-1">
            <Button
              onClick={() => {
                void autotaskApi.portalCategories
                  .download({
                    category,
                    documentId: row.original.id,
                    fileName: row.original.originalFilename,
                  })
                  .then((result) => {
                    if (!result.cancelled) {
                      toast.success("已保存");
                    }
                  })
                  .catch((error: unknown) => {
                    toast.error(
                      error instanceof Error ? error.message : "下载失败"
                    );
                  });
              }}
              size="sm"
              variant="outline"
            >
              <Download className="mr-1 h-3 w-3" />
              下载
            </Button>
            <Button
              onClick={() => setPendingDelete(row.original)}
              size="sm"
              variant="ghost"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        ),
      },
    ],
    [category]
  );

  const onUpload = async () => {
    const picked = await selectCategoryDocumentFiles();
    if (picked.cancelled || picked.files.length === 0) {
      return;
    }
    try {
      await uploadMutation.mutateAsync(picked.files.map((file) => file.path));
      toast.success("已上传");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "上传失败");
    }
  };

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader
        description={`${label}（${category}）的操作手册等文档，该分类下所有门户共用`}
        title={label}
      >
        <div className="flex items-center gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/portal-categories">返回分类</Link>
          </Button>
          <Button
            disabled={uploadMutation.isPending}
            onClick={() => void onUpload()}
            size="sm"
          >
            <Upload className="mr-1 h-4 w-4" />
            上传
          </Button>
        </div>
      </PageHeader>
      {documents.length === 0 ? (
        <EmptyState
          description="上传 .doc / .docx / .pdf 等文件，客服和运维都可以维护"
          title="还没有文档"
        />
      ) : (
        <DataTable columns={columns} data={documents} />
      )}
      <ConfirmDialog
        confirmLabel="确认删除"
        description={
          pendingDelete
            ? `确定删除 ${pendingDelete.originalFilename}？`
            : ""
        }
        onConfirm={() => {
          if (!pendingDelete) {
            return;
          }
          deleteMutation.mutate(pendingDelete.id, {
            onSuccess: () => {
              setPendingDelete(null);
              toast.success("已删除");
            },
            onError: (error) => {
              toast.error(error instanceof Error ? error.message : "删除失败");
            },
          });
        }}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDelete(null);
          }
        }}
        open={Boolean(pendingDelete)}
        title="删除文档"
      />
    </div>
  );
}
