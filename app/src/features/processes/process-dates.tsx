import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProcessInstance } from "@/features/processes/api/use-process-instances";
import { isLineEditable } from "@/features/processes/process-model";
import { ProcessOrderLinesTable } from "@/features/processes/process-order-lines-table";
import { ErpOrderLabel } from "@/features/processes/erp-order-label";
import {
  resolvePortalCustomerName,
  usePortalNameMap,
} from "@/features/processes/use-portal-name-map";
import { isCanonicalDate } from "@/features/tasks/delivery-date-task-model";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

export function ProcessDatesPage({ instanceId }: { instanceId: string }) {
  const queryClient = useQueryClient();
  const { data: detail, isLoading } = useProcessInstance(instanceId);
  const portalNameMap = usePortalNameMap();
  const [draftDates, setDraftDates] = useState<Record<string, string>>({});
  const [savingLine, setSavingLine] = useState<string | null>(null);
  const [savingAll, setSavingAll] = useState(false);

  const linesSignature = useMemo(
    () =>
      JSON.stringify(
        (detail?.lines ?? []).map((line) => [
          line.id,
          line.lineNumber,
          line.expectedDeliveryDate ?? "",
          line.lineStatus,
        ])
      ),
    [detail?.lines]
  );

  useEffect(() => {
    if (!detail) {
      return;
    }
    const next: Record<string, string> = {};
    for (const line of detail.lines) {
      next[line.lineNumber] = line.expectedDeliveryDate ?? "";
    }
    setDraftDates(next);
  }, [detail?.id, linesSignature]);

  const onRefresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.processInstances.all });
  };

  if (isLoading) {
    return <MockLoading />;
  }
  if (!detail) {
    return (
      <div className="space-y-4">
        <PageHeader title="填写交货日期" />
        <p className="text-muted-foreground text-sm">流程实例不存在或已被删除。</p>
      </div>
    );
  }

  const stageEditable =
    detail.status === "ACTIVE" &&
    (detail.stage === "SDMS_CREATED" || detail.stage === "DATES_PARTIAL");

  const dirtyLines = detail.lines.filter((line) => {
    if (
      !isLineEditable(detail.stage, detail.status, line.lineStatus) ||
      savingLine === line.lineNumber
    ) {
      return false;
    }
    const date = draftDates[line.lineNumber] ?? "";
    return (
      date !== (line.expectedDeliveryDate ?? "") && isCanonicalDate(date)
    );
  });
  const hasInvalidDraft = detail.lines.some((line) => {
    const date = draftDates[line.lineNumber] ?? "";
    return date !== "" && !isCanonicalDate(date);
  });
  const busy = savingAll || savingLine !== null;
  const canSaveAll =
    stageEditable && dirtyLines.length > 0 && !hasInvalidDraft && !busy;
  const customerName = resolvePortalCustomerName(
    portalNameMap,
    detail.portalAccountId
  );

  const updateDate = (lineNumber: string, value: string) => {
    setDraftDates((current) => ({ ...current, [lineNumber]: value }));
  };

  const submitLine = async (lineNumber: string, date: string) => {
    await autotaskApi.processInstances.submitLineDate({
      instanceId,
      lineNumber,
      expectedDeliveryDate: date,
    });
  };

  const saveOne = async (lineNumber: string) => {
    const line = detail.lines.find((item) => item.lineNumber === lineNumber);
    if (!line) {
      return;
    }
    const date = draftDates[lineNumber] ?? "";
    if (
      !isLineEditable(detail.stage, detail.status, line.lineStatus) ||
      !isCanonicalDate(date) ||
      date === (line.expectedDeliveryDate ?? "")
    ) {
      return;
    }
    setSavingLine(lineNumber);
    try {
      await submitLine(lineNumber, date);
      toast.success(`第 ${lineNumber} 行交货日期已提交写入`);
      onRefresh();
    } catch (error) {
      toast.error(errorMessage(error, "提交交货日期失败"));
    } finally {
      setSavingLine(null);
    }
  };

  const saveAll = async () => {
    if (!canSaveAll) {
      return;
    }
    setSavingAll(true);
    let successCount = 0;
    const failures: string[] = [];
    try {
      for (const line of dirtyLines) {
        const date = draftDates[line.lineNumber] ?? "";
        try {
          await submitLine(line.lineNumber, date);
          successCount += 1;
        } catch (error) {
          failures.push(
            `行 ${line.lineNumber}: ${errorMessage(error, "提交失败")}`
          );
        }
      }
      if (successCount > 0) {
        toast.success(`已提交 ${successCount} 行交货日期写入`);
        onRefresh();
      }
      if (failures.length > 0) {
        toast.error(failures.join("；"));
      }
    } finally {
      setSavingAll(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        description={`客户订单 ${detail.bizKey}：可逐行保存，也可一次保存多行；每行保存都会触发一次门户写入`}
        title="填写交货日期"
      >
        <Button asChild variant="outline">
          <Link params={{ instanceId }} to="/processes/$instanceId">
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回详情
          </Link>
        </Button>
      </PageHeader>

      <Card>
        <CardHeader className="gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">预计交货日期</CardTitle>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-muted-foreground text-sm">
                已写入 {detail.lineDone}/{detail.lineTotal}
              </span>
              {stageEditable && (
                <Button
                  disabled={!canSaveAll}
                  onClick={saveAll}
                  type="button"
                >
                  <Save className="mr-1 h-4 w-4" />
                  {savingAll
                    ? "提交中…"
                    : dirtyLines.length > 0
                      ? `保存全部（${dirtyLines.length}）`
                      : "保存全部"}
                </Button>
              )}
            </div>
          </div>
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <span>客户订单：{display(detail.summary.poNo ?? detail.bizKey)}</span>
            <span>客户：{customerName}</span>
            <span>交易主体：{display(detail.summary.supplierName)}</span>
            <ErpOrderLabel
              headerId={detail.summary.headerId}
              orderNumber={detail.summary.orderNumber}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!stageEditable && (
            <p className="text-muted-foreground text-sm">
              当前阶段不允许填写交货日期（仅「待填写交期 / 交期填写中」可编辑）。
            </p>
          )}
          {stageEditable && (
            <p className="text-muted-foreground text-sm">
              可先填多行，再点「保存全部」一次提交；也可点行内「保存」只提交该行。
            </p>
          )}
          <ProcessOrderLinesTable
            draftDates={draftDates}
            isEditableLine={(line) =>
              isLineEditable(detail.stage, detail.status, line.lineStatus)
            }
            lines={detail.lines}
            mode="edit"
            onDateChange={updateDate}
            onSaveLine={saveOne}
            savingAll={savingAll}
            savingLine={savingLine}
          />
        </CardContent>
      </Card>
    </div>
  );
}
