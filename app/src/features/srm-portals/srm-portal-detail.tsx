import { Pencil } from "lucide-react";
import { useState } from "react";
import { PortalActions } from "@/components/business/portal-actions";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalAccount } from "@/features/srm-portals/api/use-portal-accounts";
import { PortalAccountFormDialog } from "@/features/srm-portals/components/portal-account-form-dialog";
import { usePortalWritePermission } from "@/features/srm-portals/hooks/use-portal-write-permission";
import { WorkflowBindingManager } from "@/features/workflows/workflow-binding-manager";
import { formatBeijingDateTime } from "@/utils/date-time";

const openModeLabels = {
  webcontents: "内置 Web 工作区",
  system_browser: "系统浏览器",
} as const;

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Label className="text-muted-foreground">{label}</Label>
      <Input className="mt-1" readOnly value={value} />
    </div>
  );
}

export function SrmPortalDetailPage({ portalId }: { portalId: string }) {
  const [editOpen, setEditOpen] = useState(false);
  const canWrite = usePortalWritePermission((s) => s.canWrite);

  const {
    data: portal,
    isLoading,
    isError,
    refetch,
  } = usePortalAccount(portalId);

  if (isLoading) {
    return <MockLoading />;
  }

  if (isError) {
    return (
      <div className="space-y-4">
        <EmptyState description="无法加载门户详情" title="加载失败" />
        <div className="flex justify-center">
          <Button onClick={() => refetch()} variant="outline">
            重试
          </Button>
        </div>
      </div>
    );
  }

  if (!portal) {
    return <EmptyState title="门户不存在" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-bold text-2xl">{portal.portalName}</h2>
          <p className="text-muted-foreground">{portal.erpEntityName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canWrite && (
            <Button onClick={() => setEditOpen(true)} variant="outline">
              <Pencil className="mr-2 h-4 w-4" />
              编辑
            </Button>
          )}
          <PortalActions portal={portal} />
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-4 pt-4 sm:grid-cols-2">
          <Field
            label="实体类型"
            value={portal.entityType === "SUPPLIER" ? "供应商" : "客户"}
          />
          <Field
            label={portal.entityType === "SUPPLIER" ? "供应商编号" : "客户编号"}
            value={portal.erpEntityCode}
          />
          <Field
            label={portal.entityType === "SUPPLIER" ? "供应商名称" : "客户名称"}
            value={portal.erpEntityName}
          />
          <Field label="业务实体" value={portal.businessEntity || "—"} />
          <Field label="我方公司编号" value={portal.ou || "—"} />
          <Field label="门户名称" value={portal.portalName} />
          <Field label="门户地址" value={portal.portalUrl} />
          <Field label="登录账号" value={portal.loginAccount || "-"} />
          <Field
            label="打开方式"
            value={openModeLabels[portal.clientOpenMode]}
          />
          <Field label="Session 分区" value={portal.clientSessionPartition} />
          <div>
            <Label className="text-muted-foreground">状态</Label>
            <div className="mt-1">
              <Badge
                variant={portal.status === "ENABLED" ? "default" : "secondary"}
              >
                {portal.status === "ENABLED" ? "启用" : "禁用"}
              </Badge>
            </div>
          </div>
          <Field
            label="创建时间（北京时间）"
            value={formatBeijingDateTime(portal.createdAt)}
          />
          <Field
            label="更新时间（北京时间）"
            value={formatBeijingDateTime(portal.updatedAt)}
          />
        </CardContent>
      </Card>

      <PortalAccountFormDialog
        mode="edit"
        onOpenChange={setEditOpen}
        open={editOpen}
        portal={portal}
      />

      <WorkflowBindingManager portal={portal} />
    </div>
  );
}
