import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Archive,
  Ban,
  Calendar,
  Check,
  FileSignature,
  RotateCcw,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useProcessInstance } from "@/features/processes/api/use-process-instances";
import {
  MAIN_STAGES,
  formatProcessError,
  resolveProcessBlocker,
  stageName,
  stageProgressIndex,
  statusLabel,
} from "@/features/processes/process-model";
import { ProcessOrderLinesTable } from "@/features/processes/process-order-lines-table";
import { ErpOrderLabel } from "@/features/processes/erp-order-label";
import { ProcessSubTaskTree } from "@/features/processes/process-subtask-tree";
import {
  resolvePortalCustomerName,
  usePortalNameMap,
} from "@/features/processes/use-portal-name-map";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { ProcessInstanceDetail } from "@/types/process-instance";
import { formatBeijingDateTime } from "@/utils/date-time";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function StageProgress({ detail }: { detail: ProcessInstanceDetail }) {
  const currentIndex = stageProgressIndex(detail.stage);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {MAIN_STAGES.map((stage, index) => {
        const reached = currentIndex >= index;
        const isCurrent = currentIndex === index && detail.status === "ACTIVE";
        return (
          <div className="flex items-center gap-2" key={stage}>
            {index > 0 && <div className="h-px w-6 bg-border" />}
            <div
              className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${
                isCurrent
                  ? "border-primary text-primary"
                  : reached
                    ? "border-primary/40 text-foreground"
                    : "text-muted-foreground"
              }`}
            >
              {reached && !isCurrent && <Check className="h-3 w-3" />}
              {stageName(stage)}
            </div>
          </div>
        );
      })}
      {detail.stage === "FAILED" && (
        <Badge variant="destructive">
          失败：
          {formatProcessError(detail.lastErrorCode, detail.lastErrorMessage) ||
            "未知原因"}
        </Badge>
      )}
    </div>
  );
}

function StageActions({
  detail,
  onUpdated,
}: {
  detail: ProcessInstanceDetail;
  onUpdated: () => void;
}) {
  const [acting, setActing] = useState(false);

  const run = async (action: () => Promise<unknown>, successMessage: string) => {
    setActing(true);
    try {
      await action();
      toast.success(successMessage);
      onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setActing(false);
    }
  };

  if (detail.status === "COMPLETED" || detail.status === "CANCELLED") {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {(detail.stage === "SDMS_CREATED" || detail.stage === "DATES_PARTIAL") && (
        <Button asChild>
          <Link
            params={{ instanceId: detail.id }}
            to="/processes/$instanceId/dates"
          >
            <Calendar className="mr-1 h-4 w-4" />
            填写交货日期
          </Link>
        </Button>
      )}
      {detail.stage === "DATES_COMPLETE" && (
        <Button
          disabled={acting}
          onClick={() =>
            run(
              () => autotaskApi.processInstances.sign(detail.id),
              "已发起签章子任务"
            )
          }
          type="button"
        >
          <FileSignature className="mr-1 h-4 w-4" />
          去签章
        </Button>
      )}
      {detail.stage === "SIGNED" && (
        <Button
          disabled={acting}
          onClick={() =>
            run(
              () => autotaskApi.processInstances.archive(detail.id),
              "已手动触发签章合同下载与上传"
            )
          }
          type="button"
          variant="outline"
        >
          <Archive className="mr-1 h-4 w-4" />
          手动触发签章合同下载
        </Button>
      )}
      {detail.status === "FAILED" && (
        <Button
          disabled={acting}
          onClick={() =>
            run(() => autotaskApi.processInstances.retry(detail.id), "已重试")
          }
          type="button"
        >
          <RotateCcw className="mr-1 h-4 w-4" />
          重试
        </Button>
      )}
      <Button
        disabled={acting}
        onClick={() =>
          run(() => autotaskApi.processInstances.cancel(detail.id), "已取消")
        }
        type="button"
        variant="outline"
      >
        <Ban className="mr-1 h-4 w-4" />
        取消
      </Button>
    </div>
  );
}

export function ProcessDetailPage({ instanceId }: { instanceId: string }) {
  const queryClient = useQueryClient();
  const { data: detail, isLoading } = useProcessInstance(instanceId);
  const portalNameMap = usePortalNameMap();

  const onUpdated = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.processInstances.all });
  };

  if (isLoading) {
    return <MockLoading />;
  }
  if (!detail) {
    return (
      <div className="space-y-4">
        <PageHeader title="客户订单流程实例详情" />
        <p className="text-muted-foreground text-sm">流程实例不存在或已被删除。</p>
      </div>
    );
  }

  const blocker = resolveProcessBlocker(detail);
  const customerName = resolvePortalCustomerName(
    portalNameMap,
    detail.portalAccountId
  );

  return (
    <div className="space-y-4">
      <PageHeader
        description={detail.title}
        title={`客户订单 ${detail.bizKey}`}
      >
        <StageActions detail={detail} onUpdated={onUpdated} />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        <Badge className="text-sm" variant="default">
          阶段：{stageName(detail.stage)}
        </Badge>
        <Badge className="text-sm" variant="secondary">
          运行状态：{statusLabel(detail.status)}
        </Badge>
      </div>

      {blocker && (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm"
          role="status"
        >
          <p className="font-medium text-destructive">{blocker.title}</p>
          <p className="mt-1 text-foreground">{blocker.message}</p>
          {blocker.errorCode && (
            <p className="mt-1 text-muted-foreground text-xs">
              错误码：{blocker.errorCode}
            </p>
          )}
          <p className="mt-1 text-muted-foreground text-xs">
            可在下方「子任务与执行记录」查看详情；阶段未变时可重试对应操作。
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">流程进度</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <StageProgress detail={detail} />
          {detail.stage === "SIGN_REQUESTED" && detail.status === "ACTIVE" && (
            <p className="text-muted-foreground text-sm">
              双方盖章进行中（客户→我司），阶段保持「待回签」。系统轮询 SRM
              变为「已回签」后再自动下载双方签章合同上传；也可在列表点「立即回签轮询」。此阶段不提供合同下载。
            </p>
          )}
          {detail.stage === "DATES_COMPLETE" && detail.status === "ACTIVE" && (
            <p className="text-muted-foreground text-sm">
              演示 TEMP：若门户该单已是「已回签」，可在列表点「立即回签轮询」探测并自动归档。
            </p>
          )}
          {detail.stage === "SIGNED" && detail.status === "ACTIVE" && (
            <p className="text-muted-foreground text-sm">
              已确认 SRM「已回签」。系统会自动下载双方签章合同并上传；若失败请用「手动触发签章合同下载」重试。
            </p>
          )}
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <span>客户订单：{display(detail.summary.poNo ?? detail.bizKey)}</span>
            <span>客户：{customerName}</span>
            <span>交易主体：{display(detail.summary.supplierName)}</span>
            <ErpOrderLabel
              headerId={detail.summary.headerId}
              orderNumber={detail.summary.orderNumber}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">订单行</CardTitle>
            <span className="text-muted-foreground text-sm">
              已写入 {detail.lineDone}/{detail.lineTotal}
            </span>
          </div>
          {(detail.stage === "SDMS_CREATED" ||
            detail.stage === "DATES_PARTIAL") &&
            detail.status === "ACTIVE" && (
              <p className="text-muted-foreground text-sm">
                本页订单行为只读预览。请点击右上角「填写交货日期」进入编辑页，逐行填写并保存。
              </p>
            )}
        </CardHeader>
        <CardContent>
          <ProcessOrderLinesTable lines={detail.lines} mode="readonly" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">子任务与执行记录</CardTitle>
        </CardHeader>
        <CardContent>
          <ProcessSubTaskTree tasks={detail.subTasks} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">阶段历史</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间（北京时间）</TableHead>
                <TableHead>从</TableHead>
                <TableHead>到</TableHead>
                <TableHead>操作者</TableHead>
                <TableHead>备注</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.stageHistory.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{formatBeijingDateTime(item.createdAt)}</TableCell>
                  <TableCell>{item.fromStage ?? "—"}</TableCell>
                  <TableCell>{item.toStage}</TableCell>
                  <TableCell>{item.actor}</TableCell>
                  <TableCell>{item.note ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
