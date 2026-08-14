import type { CSSProperties } from "react";
import { Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatProcessError, lineStatusLabel } from "@/features/processes/process-model";
import { isCanonicalDate } from "@/features/tasks/delivery-date-task-model";
import type { ProcessLineItem } from "@/types/process-instance";
import { cn } from "@/utils/tailwind";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

/** SRM 只读列（横向滚动）；AutoTask 列固定在右侧 */
const SRM_SCROLL_HEADERS = [
  "订单行号",
  "料号",
  "料品名称",
  "料品规格",
  "物料状态",
  "内码",
  "数量",
  "单位",
  "单价（元）",
  "价税合计（元）",
  "要求交货日期",
  "标准交货日期（天）",
  "是否满足LT",
  "供方交期",
  "欠交数量",
  "备注",
  "直发备注",
] as const;

/** 右侧固定列宽度（与 sticky right 偏移一致） */
const STICKY_ACTION_W = "5.5rem";
const STICKY_STATUS_W = "7rem";
const STICKY_DATE_W = "10rem";

function stickySurface(options: { edge?: boolean; head?: boolean } = {}) {
  return cn(
    "sticky z-20 bg-background group-hover:bg-muted/50",
    options.head && "z-30",
    options.edge && "border-l shadow-[-6px_0_8px_-6px_rgba(0,0,0,0.12)]"
  );
}

function LineStatusCell({
  line,
  className,
  style,
}: {
  line: ProcessLineItem;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <TableCell
      className={cn("min-w-28 whitespace-normal", className)}
      style={style}
    >
      <Badge
        variant={
          line.lineStatus === "WRITE_FAILED"
            ? "destructive"
            : line.lineStatus === "WRITTEN"
              ? "default"
              : "outline"
        }
      >
        {lineStatusLabel(line.lineStatus)}
      </Badge>
      {line.lastErrorMessage && (
        <p className="mt-1 text-destructive text-xs">
          {formatProcessError(line.lastErrorCode, line.lastErrorMessage)}
        </p>
      )}
    </TableCell>
  );
}

function SrmLineCells({ line }: { line: ProcessLineItem }) {
  return (
    <>
      <TableCell>{line.lineNumber}</TableCell>
      <TableCell>{line.materialNumber}</TableCell>
      <TableCell className="max-w-48 whitespace-normal">
        {display(line.itemName)}
      </TableCell>
      <TableCell className="max-w-48 whitespace-normal">
        {display(line.itemSpecification)}
      </TableCell>
      <TableCell>{display(line.materialStatus)}</TableCell>
      <TableCell>{display(line.internalCode)}</TableCell>
      <TableCell>{display(line.orderQuantity)}</TableCell>
      <TableCell>{display(line.orderQuantityUom)}</TableCell>
      <TableCell>{display(line.unitSellingPrice)}</TableCell>
      <TableCell>{display(line.taxIncludedAmount)}</TableCell>
      <TableCell>{display(line.requestDate)}</TableCell>
      <TableCell>{display(line.standardDeliveryDays)}</TableCell>
      <TableCell>{display(line.meetsLeadTime)}</TableCell>
      <TableCell>{display(line.supplierDeliveryDate)}</TableCell>
      <TableCell>{display(line.outstandingQuantity)}</TableCell>
      <TableCell className="max-w-40 whitespace-normal">
        {display(line.remarks)}
      </TableCell>
      <TableCell className="max-w-40 whitespace-normal">
        {display(line.directShipmentRemarks)}
      </TableCell>
    </>
  );
}

interface ProcessOrderLinesTableProps {
  lines: ProcessLineItem[];
  mode: "readonly" | "edit";
  draftDates?: Record<string, string>;
  onDateChange?: (lineNumber: string, value: string) => void;
  onSaveLine?: (lineNumber: string) => void;
  isEditableLine?: (line: ProcessLineItem) => boolean;
  savingLine?: string | null;
  savingAll?: boolean;
}

export function ProcessOrderLinesTable({
  lines,
  mode,
  draftDates = {},
  onDateChange,
  onSaveLine,
  isEditableLine,
  savingLine = null,
  savingAll = false,
}: ProcessOrderLinesTableProps) {
  const showActions = mode === "edit";
  const colSpan = SRM_SCROLL_HEADERS.length + 2 + (showActions ? 1 : 0);

  // 从右往左：操作 → 行状态 → 预计交货日期
  const actionRight = "0px";
  const statusRight = showActions ? STICKY_ACTION_W : "0px";
  const dateRight = showActions
    ? `calc(${STICKY_ACTION_W} + ${STICKY_STATUS_W})`
    : STICKY_STATUS_W;

  return (
    <Table>
      <TableHeader>
        <TableRow className="group">
          {SRM_SCROLL_HEADERS.map((label) => (
            <TableHead className="whitespace-nowrap" key={label}>
              {label}
            </TableHead>
          ))}
          <TableHead
            className={cn(
              "whitespace-nowrap",
              stickySurface({ edge: true, head: true })
            )}
            style={{
              right: dateRight,
              width: STICKY_DATE_W,
              minWidth: STICKY_DATE_W,
            }}
          >
            预计交货日期
          </TableHead>
          <TableHead
            className={cn("whitespace-nowrap", stickySurface({ head: true }))}
            style={{
              right: statusRight,
              width: STICKY_STATUS_W,
              minWidth: STICKY_STATUS_W,
            }}
          >
            行状态
          </TableHead>
          {showActions && (
            <TableHead
              className={cn("whitespace-nowrap", stickySurface({ head: true }))}
              style={{
                right: actionRight,
                width: STICKY_ACTION_W,
                minWidth: STICKY_ACTION_W,
              }}
            >
              操作
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {lines.map((line) => {
          const date = draftDates[line.lineNumber] ?? "";
          const editable = Boolean(isEditableLine?.(line));
          const invalid = date !== "" && !isCanonicalDate(date);
          const dirty = date !== (line.expectedDeliveryDate ?? "");
          const saving = savingAll || savingLine === line.lineNumber;
          const canSave =
            editable &&
            dirty &&
            !invalid &&
            isCanonicalDate(date) &&
            !saving;

          return (
            <TableRow className="group" key={line.id}>
              <SrmLineCells line={line} />
              <TableCell
                className={stickySurface({ edge: true })}
                style={{
                  right: dateRight,
                  width: STICKY_DATE_W,
                  minWidth: STICKY_DATE_W,
                }}
              >
                {mode === "edit" && editable ? (
                  <>
                    <Input
                      aria-label={`第 ${line.lineNumber} 行预计交货日期`}
                      max="9999-12-31"
                      min="0001-01-01"
                      onChange={(event) =>
                        onDateChange?.(line.lineNumber, event.target.value)
                      }
                      type="date"
                      value={date}
                    />
                    {invalid && (
                      <p className="mt-1 text-destructive text-xs">
                        日期格式不正确
                      </p>
                    )}
                  </>
                ) : (
                  display(line.expectedDeliveryDate)
                )}
              </TableCell>
              <LineStatusCell
                className={stickySurface()}
                line={line}
                style={{
                  right: statusRight,
                  width: STICKY_STATUS_W,
                  minWidth: STICKY_STATUS_W,
                }}
              />
              {showActions && (
                <TableCell
                  className={stickySurface()}
                  style={{
                    right: actionRight,
                    width: STICKY_ACTION_W,
                    minWidth: STICKY_ACTION_W,
                  }}
                >
                  {editable && (
                    <Button
                      disabled={!canSave}
                      onClick={() => onSaveLine?.(line.lineNumber)}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      <Save className="mr-1 h-4 w-4" />
                      {saving ? "提交中…" : "保存"}
                    </Button>
                  )}
                </TableCell>
              )}
            </TableRow>
          );
        })}
        {lines.length === 0 && (
          <TableRow>
            <TableCell
              className="text-center text-muted-foreground"
              colSpan={colSpan}
            >
              建单完成后自动写入订单行
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
