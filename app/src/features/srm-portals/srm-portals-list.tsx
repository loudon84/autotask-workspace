import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { PortalActions } from "@/components/business/portal-actions";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useDeletePortalAccount,
  useDisablePortalAccount,
} from "@/features/srm-portals/api/use-portal-account-mutations";
import { usePortalAccounts } from "@/features/srm-portals/api/use-portal-accounts";
import { PortalAccountFormDialog } from "@/features/srm-portals/components/portal-account-form-dialog";
import { formatOwnerLabel } from "@/features/srm-portals/owner-label";
import { portalCategoryLabel } from "@/features/srm-portals/portal-category";
import { usePortalWritePermission } from "@/features/srm-portals/hooks/use-portal-write-permission";
import type { PortalAccount, PortalStatus } from "@/types/portal-account";
import type { ClientOpenMode } from "@/types/web-tab";
import { formatBeijingDateTime } from "@/utils/date-time";
import { cn } from "@/utils/tailwind";

function TruncatedCell({
  value,
  className,
  empty = "—",
}: {
  value: string | undefined;
  className?: string;
  empty?: string;
}) {
  const text = value?.trim() || empty;
  return (
    <span
      className={cn("inline-block max-w-[11rem] truncate align-middle", className)}
      title={text === empty ? undefined : text}
    >
      {text}
    </span>
  );
}

interface PortalRowActionsProps {
  canWrite: boolean;
  onEdit: (portal: PortalAccount) => void;
  portal: PortalAccount;
}

function PortalRowActions({ portal, canWrite, onEdit }: PortalRowActionsProps) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const disableMutation = useDisablePortalAccount();
  const deleteMutation = useDeletePortalAccount();

  return (
    <div className="flex flex-nowrap items-center gap-1">
      <PortalActions compact portal={portal} />
      {canWrite && (
        <>
          <Button
            disabled={portal.status === "DISABLED"}
            onClick={() => disableMutation.mutate(portal.id)}
            size="sm"
            variant="outline"
          >
            禁用
          </Button>
          <Button onClick={() => onEdit(portal)} size="sm" variant="outline">
            <Pencil className="mr-1 h-3 w-3" />
            编辑
          </Button>
          <Button onClick={() => setDeleteOpen(true)} size="sm" variant="ghost">
            <Trash2 className="h-3 w-3" />
          </Button>
          <ConfirmDialog
            confirmLabel="确认删除"
            description={`确定要删除 ${portal.portalName} 吗？此操作为软删除。`}
            onConfirm={() => {
              deleteMutation.mutate(portal.id, {
                onSuccess: () => setDeleteOpen(false),
              });
            }}
            onOpenChange={setDeleteOpen}
            open={deleteOpen}
            title="删除门户"
          />
        </>
      )}
    </div>
  );
}

function buildColumns(
  canWrite: boolean,
  onEdit: (portal: PortalAccount) => void
): ColumnDef<PortalAccount>[] {
  return [
    {
      accessorKey: "entityType",
      header: "实体类型",
      cell: ({ row }) =>
        row.original.entityType === "SUPPLIER" ? "供应商" : "客户",
    },
    { accessorKey: "erpEntityCode", header: "编号" },
    {
      accessorKey: "erpEntityName",
      header: "portal名称",
      cell: ({ row }) => (
        <TruncatedCell
          className="max-w-[9rem]"
          value={row.original.erpEntityName}
        />
      ),
    },
    {
      accessorKey: "category",
      header: "分类",
      cell: ({ row }) => (
        <TruncatedCell value={portalCategoryLabel(row.original.category)} />
      ),
    },
    {
      accessorKey: "businessEntity",
      header: "业务实体",
      cell: ({ row }) => <TruncatedCell value={row.original.businessEntity} />,
    },
    {
      accessorKey: "portalName",
      header: "门户名称",
      cell: ({ row }) => (
        <Link
          className="inline-block max-w-[9rem] truncate hover:underline"
          params={{ portalId: row.original.id }}
          title={row.original.portalName}
          to="/srm-portals/$portalId"
        >
          {row.original.portalName}
        </Link>
      ),
    },
    {
      accessorKey: "portalUrl",
      header: "门户地址",
      cell: ({ row }) => (
        <TruncatedCell
          className="max-w-[10rem] font-mono text-xs"
          value={row.original.portalUrl}
        />
      ),
    },
    {
      accessorKey: "loginAccount",
      header: "登录账号",
      cell: ({ row }) => (
        <TruncatedCell
          className="max-w-[8rem] font-mono text-xs"
          value={row.original.loginAccount}
        />
      ),
    },
    {
      accessorKey: "createdByName",
      header: "创建人",
      cell: ({ row }) => (
        <TruncatedCell
          className="max-w-[8rem]"
          value={
            formatOwnerLabel(row.original.createdByName) ||
            row.original.createdBy
          }
        />
      ),
    },
    {
      accessorKey: "ownerName",
      header: "归属人",
      cell: ({ row }) => (
        <TruncatedCell
          className="max-w-[8rem]"
          value={formatOwnerLabel(row.original.ownerName) || row.original.ownerUserId}
        />
      ),
    },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => (
        <Badge
          variant={row.original.status === "ENABLED" ? "default" : "secondary"}
        >
          {row.original.status === "ENABLED" ? "启用" : "禁用"}
        </Badge>
      ),
    },
    {
      accessorKey: "updatedAt",
      header: "更新时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
    },
    {
      id: "actions",
      header: "操作",
      meta: { sticky: "right" },
      cell: ({ row }) => (
        <PortalRowActions
          canWrite={canWrite}
          onEdit={onEdit}
          portal={row.original}
        />
      ),
    },
  ];
}

export function SrmPortalsListPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<PortalStatus | "ALL">("ALL");
  const [openModeFilter, setOpenModeFilter] = useState<ClientOpenMode | "ALL">(
    "ALL"
  );
  const [formOpen, setFormOpen] = useState(false);
  const [editingPortal, setEditingPortal] = useState<
    PortalAccount | undefined
  >();

  const canWrite = usePortalWritePermission((s) => s.canWrite);
  const {
    data: portals = [],
    isLoading,
    isError,
    refetch,
  } = usePortalAccounts();

  const filteredPortals = useMemo(() => {
    const q = search.trim().toLowerCase();
    return portals.filter((portal) => {
      if (statusFilter !== "ALL" && portal.status !== statusFilter) {
        return false;
      }
      if (
        openModeFilter !== "ALL" &&
        portal.clientOpenMode !== openModeFilter
      ) {
        return false;
      }
      if (!q) {
        return true;
      }
      return (
        portal.erpEntityCode.toLowerCase().includes(q) ||
        portal.erpEntityName.toLowerCase().includes(q) ||
        portal.portalName.toLowerCase().includes(q) ||
        portal.loginAccount.toLowerCase().includes(q)
      );
    });
  }, [portals, search, statusFilter, openModeFilter]);

  const handleEdit = (portal: PortalAccount) => {
    setEditingPortal(portal);
    setFormOpen(true);
  };

  const handleCreate = () => {
    setEditingPortal(undefined);
    setFormOpen(true);
  };

  if (isLoading) {
    return <MockLoading />;
  }

  if (isError) {
    return (
      <div className="space-y-4">
        <EmptyState
          description="无法加载门户列表，请检查网络或登录状态"
          title="加载失败"
        />
        <div className="flex justify-center">
          <Button onClick={() => refetch()} variant="outline">
            重试
          </Button>
        </div>
      </div>
    );
  }

  const columns = buildColumns(canWrite, handleEdit);

  return (
    <div className="space-y-4">
      <PageHeader
        description="维护客户与供应商的门户登录与基础信息"
        title="客户/供应商门户"
      >
        {canWrite && (
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" />
            新增门户
          </Button>
        )}
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="max-w-xs"
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索主体/门户/账号"
          value={search}
        />
        <Select
          onValueChange={(v) => setStatusFilter(v as PortalStatus | "ALL")}
          value={statusFilter}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部状态</SelectItem>
            <SelectItem value="ENABLED">启用</SelectItem>
            <SelectItem value="DISABLED">禁用</SelectItem>
          </SelectContent>
        </Select>
        <Select
          onValueChange={(v) => setOpenModeFilter(v as ClientOpenMode | "ALL")}
          value={openModeFilter}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="打开方式" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部方式</SelectItem>
            <SelectItem value="webcontents">内置 Web</SelectItem>
            <SelectItem value="system_browser">系统浏览器</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={() => refetch()} size="icon" variant="outline">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {filteredPortals.length === 0 ? (
        <div className="space-y-4">
          <EmptyState
            description={
              portals.length === 0 ? "暂无门户配置" : "没有符合筛选条件的门户"
            }
            title="暂无数据"
          />
          {canWrite && portals.length === 0 && (
            <div className="flex justify-center">
              <Button onClick={handleCreate} variant="outline">
                新增门户
              </Button>
            </div>
          )}
        </div>
      ) : (
        <DataTable columns={columns} data={filteredPortals} />
      )}

      <PortalAccountFormDialog
        mode={editingPortal ? "edit" : "create"}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingPortal(undefined);
          }
        }}
        open={formOpen}
        portal={editingPortal}
      />
    </div>
  );
}
