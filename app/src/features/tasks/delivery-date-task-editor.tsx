import { Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  type DeliveryDateLine,
  deliveryDateSignature,
  displayTaskValue,
  isCanonicalDate,
  parseDeliveryDateLines,
} from "@/features/tasks/delivery-date-task-model";
import { autotaskApi } from "@/services/autotask-api";
import type { AutomationTaskStatus } from "@/types/automation-task";

interface DeliveryDateTaskEditorProps {
  input: Record<string, unknown>;
  onSaved?: () => void;
  status: AutomationTaskStatus;
  taskId: string;
}

function EmptyLinesCard({ input }: { input: Record<string, unknown> }) {
  const wrongType =
    input.order_lines !== undefined && !Array.isArray(input.order_lines);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">预计交货日期</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm">
          <p className="text-destructive">
            任务输入中没有有效的 order_lines，无法维护预计交货日期。
          </p>
          <p className="text-muted-foreground">
            {wrongType
              ? "当前 order_lines 类型错误。请取消这条任务后使用新版明细表重新创建，或先运行任务 1 让系统自动生成任务 2。"
              : "正常情况下应先运行任务 1，由系统把完整订单明细传递到任务 2。"}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function OrderSummary({ input }: { input: Record<string, unknown> }) {
  return (
    <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
      <span>采购订单：{displayTaskValue(input.po_no)}</span>
      <span>ERP 订单：{displayTaskValue(input.order_number)}</span>
      <span>供应商编码：{displayTaskValue(input.supplier_code)}</span>
      <span>供应商名称：{displayTaskValue(input.supplier_name)}</span>
    </div>
  );
}

interface DeliveryDateTableProps {
  editable: boolean;
  lines: DeliveryDateLine[];
  updateDate: (index: number, value: string) => void;
}

function DeliveryDateTable({
  editable,
  lines,
  updateDate,
}: DeliveryDateTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>行号</TableHead>
          <TableHead>物料号</TableHead>
          <TableHead>物料名称 / 规格</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>需求日期</TableHead>
          <TableHead>标准交期</TableHead>
          <TableHead className="min-w-40">预计交货日期</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {lines.map((line, index) => (
          <TableRow key={`${line.lineNumber}:${line.materialNumber}`}>
            <TableCell>{displayTaskValue(line.lineNumber)}</TableCell>
            <TableCell>{displayTaskValue(line.materialNumber)}</TableCell>
            <TableCell className="max-w-72 whitespace-normal">
              <div>{displayTaskValue(line.itemName)}</div>
              {line.itemSpecification && (
                <div className="text-muted-foreground">
                  {line.itemSpecification}
                </div>
              )}
            </TableCell>
            <TableCell>
              {displayTaskValue(
                [line.orderQuantity, line.orderQuantityUom]
                  .filter(Boolean)
                  .join(" ")
              )}
            </TableCell>
            <TableCell>{displayTaskValue(line.requestDate)}</TableCell>
            <TableCell>
              {line.standardDeliveryDays
                ? `${line.standardDeliveryDays} 天`
                : "—"}
            </TableCell>
            <TableCell>
              {editable ? (
                <Input
                  aria-label={`第 ${line.lineNumber || index + 1} 行预计交货日期`}
                  max="9999-12-31"
                  min="0001-01-01"
                  onChange={(event) => updateDate(index, event.target.value)}
                  type="date"
                  value={line.expectedDeliveryDate}
                />
              ) : (
                displayTaskValue(line.expectedDeliveryDate)
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function DeliveryDateTaskEditor({
  input,
  onSaved,
  status,
  taskId,
}: DeliveryDateTaskEditorProps) {
  const sourceLines = useMemo(() => parseDeliveryDateLines(input), [input]);
  const sourceSignature = useMemo(
    () => JSON.stringify(sourceLines.map((line) => line.raw)),
    [sourceLines]
  );
  const [draftLines, setDraftLines] = useState(sourceLines);
  const [loadedSourceSignature, setLoadedSourceSignature] =
    useState(sourceSignature);
  const [savedDateSignature, setSavedDateSignature] = useState(() =>
    deliveryDateSignature(sourceLines)
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (sourceSignature === loadedSourceSignature) {
      return;
    }
    setDraftLines(sourceLines);
    setSavedDateSignature(deliveryDateSignature(sourceLines));
    setLoadedSourceSignature(sourceSignature);
  }, [loadedSourceSignature, sourceLines, sourceSignature]);

  const editable = status === "DRAFT" || status === "READY";
  const draftDateSignature = deliveryDateSignature(draftLines);
  const dirty = draftDateSignature !== savedDateSignature;
  const completedCount = draftLines.filter((line) =>
    isCanonicalDate(line.expectedDeliveryDate)
  ).length;
  const hasInvalidDate = draftLines.some(
    (line) =>
      line.expectedDeliveryDate !== "" &&
      !isCanonicalDate(line.expectedDeliveryDate)
  );

  const updateDate = (index: number, value: string) => {
    setDraftLines((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, expectedDeliveryDate: value } : line
      )
    );
  };

  const save = async () => {
    if (!(editable && dirty) || hasInvalidDate) {
      return;
    }
    setSaving(true);
    try {
      const orderLines = sourceLines.map((line, index) => ({
        ...line.raw,
        expected_delivery_date: draftLines[index]?.expectedDeliveryDate || null,
      }));
      const updated = await autotaskApi.tasks.update(taskId, {
        input: { ...input, order_lines: orderLines },
      });
      if (!updated) {
        throw new Error("任务不存在或保存后无法读取任务详情");
      }
      setSavedDateSignature(draftDateSignature);
      toast.success("预计交货日期已保存");
      onSaved?.();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "保存预计交货日期失败"
      );
    } finally {
      setSaving(false);
    }
  };

  if (sourceLines.length === 0) {
    return <EmptyLinesCard input={input} />;
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">预计交货日期</CardTitle>
          <span className="text-muted-foreground text-sm">
            已填写 {completedCount}/{draftLines.length}
          </span>
        </div>
        <OrderSummary input={input} />
      </CardHeader>
      <CardContent className="space-y-4">
        <DeliveryDateTable
          editable={editable}
          lines={draftLines}
          updateDate={updateDate}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-muted-foreground text-sm">
            {editable
              ? "可以分次保存；全部日期填写并保存后再执行任务。"
              : "任务进入队列后，输入参数不可再修改。"}
          </p>
          {editable && (
            <Button
              disabled={!dirty || hasInvalidDate || saving}
              onClick={save}
              type="button"
            >
              <Save className="mr-1 h-4 w-4" />
              {saving ? "保存中…" : "保存交货日期"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
