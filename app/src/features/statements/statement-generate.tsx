import { Link, useNavigate } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePortalAccounts } from "@/features/srm-portals/api/use-portal-accounts";
import {
  RECEIPT_LINE_FIELD_COLUMNS,
  formatAmount,
} from "@/features/statements/statement-model";
import { StatementSopProgress } from "@/features/statements/statement-sop-progress";
import { autotaskApi } from "@/services/autotask-api";
import type {
  StatementReceiptLine,
  StatementSopStepId,
} from "@/types/statement";

function cellText(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "-";
}

function rowKey(row: StatementReceiptLine): string {
  return `${row.receiptNo}::${row.lineNo}`;
}

export function StatementGeneratePage() {
  const navigate = useNavigate();
  const { data: portals = [] } = usePortalAccounts();
  const enabledPortals = portals.filter((portal) => portal.status === "ENABLED");
  const [portalAccountId, setPortalAccountId] = useState("");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [rows, setRows] = useState<StatementReceiptLine[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [searching, setSearching] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [mismatch, setMismatch] = useState<string | null>(null);
  const [sopStep, setSopStep] = useState<StatementSopStepId>("STMT_CREATING");

  useEffect(() => {
    if (portalAccountId || enabledPortals.length === 0) {
      return;
    }
    const preferred =
      enabledPortals.find((portal) => portal.portalName.includes("天地伟业")) ??
      enabledPortals[0];
    setPortalAccountId(preferred.id);
  }, [enabledPortals, portalAccountId]);

  const selectedRows = useMemo(
    () => rows.filter((row) => selected.has(rowKey(row))),
    [rows, selected]
  );
  const selectedAmount = useMemo(() => {
    return selectedRows.reduce((sum, row) => {
      const amount = Number(row.taxIncludedAmount || 0);
      return sum + (Number.isNaN(amount) ? 0 : amount);
    }, 0);
  }, [selectedRows]);

  const columns = useMemo<ColumnDef<StatementReceiptLine>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={
              rows.length > 0 && selected.size === rows.length
                ? true
                : selected.size > 0
                  ? "indeterminate"
                  : false
            }
            onCheckedChange={(checked) => {
              if (checked) {
                setSelected(new Set(rows.map(rowKey)));
              } else {
                setSelected(new Set());
              }
              void table;
            }}
          />
        ),
        cell: ({ row }) => {
          const key = rowKey(row.original);
          return (
            <Checkbox
              checked={selected.has(key)}
              onCheckedChange={(checked) => {
                setSelected((prev) => {
                  const next = new Set(prev);
                  if (checked) next.add(key);
                  else next.delete(key);
                  return next;
                });
              }}
            />
          );
        },
      },
      ...RECEIPT_LINE_FIELD_COLUMNS.map((column) => ({
        accessorKey: String(column.accessorKey),
        header: column.header,
        cell: ({ row }: { row: { original: StatementReceiptLine } }) => {
          const value = row.original[column.accessorKey];
          if (column.format === "amount") {
            return formatAmount(value as string);
          }
          return cellText(value);
        },
      })),
    ],
    [rows, selected]
  );

  const search = async () => {
    if (!portalAccountId) {
      toast.error("请选择客户门户");
      return;
    }
    if (!dateStart || !dateEnd) {
      toast.error("请选择入库确认时间起止");
      return;
    }
    setSearching(true);
    setMismatch(null);
    try {
      const task = await autotaskApi.statements.queryReceipts({
        portalAccountId,
        dateStart,
        dateEnd,
      });
      for (let i = 0; i < 60; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const result = await autotaskApi.statements.getQueryReceipts(task.taskId);
        if (result.runStatus === "SUCCESS" || result.status === "SUCCESS") {
          const nextRows = (result.rows || []).map((item) => ({
            receiptNo: String(item.receiptNo || ""),
            lineNo: String(item.lineNo || ""),
            orderNo: String(item.orderNo || ""),
            materialNumber: String(item.materialNumber || ""),
            itemName: String(item.itemName || ""),
            taxIncludedAmount: String(item.taxIncludedAmount || ""),
            inboundConfirmDate: String(item.inboundConfirmDate || ""),
            reconcileStatus: String(item.reconcileStatus || ""),
            ...item,
          }));
          setRows(nextRows);
          setSelected(new Set(nextRows.map(rowKey)));
          toast.success(`已加载 ${nextRows.length} 行`);
          return;
        }
        if (
          result.runStatus === "FAILED" ||
          result.status === "FAILED" ||
          result.errorMessage
        ) {
          throw new Error(result.errorMessage || "查询收货列表失败");
        }
      }
      throw new Error("查询超时，请稍后重试");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "查询失败");
    } finally {
      setSearching(false);
    }
  };

  const generate = async () => {
    if (selectedRows.length === 0) {
      toast.error("请至少勾选一行");
      return;
    }
    setGenerating(true);
    setMismatch(null);
    setSopStep("STMT_SDMS_CHECK");
    try {
      const result = await autotaskApi.statements.generate({
        portalAccountId,
        dateStart,
        dateEnd,
        lines: selectedRows,
      });
      toast.success(
        `已创建待生成草稿（本地汇总 ¥${result.localAmount ?? formatAmount(selectedAmount)}），正在调用 SRM`
      );
      if (result.billId) {
        void navigate({
          params: { billId: result.billId },
          to: "/process-instances/statements/$billId",
        });
      } else {
        void navigate({ to: "/process-instances/statements" });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "生成失败";
      setMismatch(message);
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        description="查询 SRM 未提交的收货列表，勾选后校验 SDMS 对账单对账金额并生成对账单"
        title="生成客户对账单"
      >
        <Button asChild size="sm" variant="outline">
          <Link to="/process-instances/statements">返回列表</Link>
        </Button>
      </PageHeader>

      <StatementSopProgress currentStep={sopStep} />

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <div className="text-muted-foreground text-xs">客户门户</div>
          <Select onValueChange={setPortalAccountId} value={portalAccountId}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="选择客户门户" />
            </SelectTrigger>
            <SelectContent>
              {enabledPortals.map((portal) => (
                <SelectItem key={portal.id} value={portal.id}>
                  {portal.portalName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <div className="text-muted-foreground text-xs">入库确认开始</div>
          <Input
            onChange={(event) => setDateStart(event.target.value)}
            type="date"
            value={dateStart}
          />
        </div>
        <div className="space-y-1">
          <div className="text-muted-foreground text-xs">入库确认结束</div>
          <Input
            onChange={(event) => setDateEnd(event.target.value)}
            type="date"
            value={dateEnd}
          />
        </div>
        <Button disabled={searching} onClick={() => void search()}>
          {searching ? "查询中…" : "搜索"}
        </Button>
      </div>

      {mismatch ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive break-all whitespace-pre-wrap">
          {mismatch}
        </div>
      ) : null}

      <DataTable columns={columns} data={rows} />

      <div className="flex items-center justify-between rounded-md border p-3 text-sm">
        <div>
          勾选 {selectedRows.length} 行，可立账价税合计汇总 ¥
          {formatAmount(selectedAmount)}
        </div>
        <Button disabled={generating} onClick={() => void generate()}>
          {generating ? "生成中…" : "生成对账单"}
        </Button>
      </div>
    </div>
  );
}
