import type {
  StatementBillListItem,
  StatementCheckStatus,
  StatementPersistedStage,
  StatementReceiptLine,
  StatementSopStepId,
} from "@/types/statement";

/** 附件 3 收货导出字段，去掉供应商编号/名称。 */
export const RECEIPT_LINE_FIELD_COLUMNS: Array<{
  accessorKey: keyof StatementReceiptLine;
  header: string;
  format?: "amount";
}> = [
  { accessorKey: "orderNo", header: "订单编号" },
  { accessorKey: "receiptNo", header: "收货单号" },
  { accessorKey: "lineNo", header: "收货单行号" },
  { accessorKey: "reconcileStatus", header: "对账状态" },
  { accessorKey: "docType", header: "单据类型" },
  { accessorKey: "inboundConfirmDate", header: "入库确认日期" },
  { accessorKey: "materialNumber", header: "料号" },
  { accessorKey: "itemName", header: "料品名称" },
  { accessorKey: "itemSpec", header: "料品规格" },
  { accessorKey: "receivedQty", header: "实收数量" },
  { accessorKey: "unitPrice", header: "单价（元）", format: "amount" },
  { accessorKey: "untaxedUnitPrice", header: "未税单价（元）", format: "amount" },
  { accessorKey: "taxRate", header: "税率" },
  { accessorKey: "untaxedAmount", header: "可立账未税金额（元）", format: "amount" },
  { accessorKey: "taxAmount", header: "可立账税额（元）", format: "amount" },
  { accessorKey: "taxIncludedAmount", header: "可立账价税合计（元）", format: "amount" },
  { accessorKey: "docDate", header: "单据日期" },
  { accessorKey: "billQty", header: "立账数量" },
  { accessorKey: "actualArrivalDate", header: "实际到货日期" },
];

export const CHECK_STATUS_LABEL: Record<StatementCheckStatus, string> = {
  DRAFT: "待生成",
  UNCHECKED: "未对账",
  CHECKED: "已对账",
  VOID: "已作废",
};

export const INVOICE_STATUS_LABEL: Record<string, string> = {
  NOT_UPLOADED: "未上传",
  UPLOADED: "已扫描",
  REVIEWING: "审批中",
};

export const SOP_MAIN_STEPS: Array<{ id: StatementSopStepId; name: string }> = [
  { id: "STMT_CREATING", name: "待创建" },
  { id: "STMT_SDMS_CHECK", name: "SDMS对账单核准" },
  { id: "STMT_GENERATING", name: "待生成" },
  { id: "STMT_PENDING_INVOICE", name: "待上传发票" },
  { id: "STMT_PENDING_REVIEW", name: "提交审核" },
  { id: "STMT_SUBMITTED", name: "已完成" },
];

export const STATEMENT_STAGE_TABS = [
  { value: "all", label: "全部" },
  { value: "STMT_GENERATING", label: "待生成" },
  { value: "STMT_PENDING_INVOICE", label: "待上传发票" },
  { value: "STMT_PENDING_REVIEW", label: "提交审核" },
  { value: "STMT_SUBMITTED", label: "已完成" },
  { value: "STMT_CANCELLED", label: "已作废" },
] as const;

export const STATEMENT_STAGE_BUTTON: Record<string, string | null> = {
  STMT_GENERATING: "重新生成",
  STMT_PENDING_INVOICE: "提交审核",
  STMT_PENDING_REVIEW: "提交审核",
  STMT_SUBMITTED: null,
  STMT_CANCELLED: null,
};

export const STATEMENT_SUBTASK_NODES = [
  { taskType: "srm_stmt_query_receipts", label: "待创建 · 查询收货" },
  { taskType: "srm_stmt_generate", label: "待生成" },
  { taskType: "srm_stmt_upload_invoice", label: "扫描发票" },
  { taskType: "srm_stmt_submit_review", label: "提交审核" },
];

export function statementStageName(stage?: string | null): string {
  if (!stage) return "—";
  if (stage === "STMT_CANCELLED") return "已作废";
  return SOP_MAIN_STEPS.find((item) => item.id === stage)?.name ?? stage;
}

export function statementStatusLabel(status?: string | null): string {
  switch (status) {
    case "ACTIVE":
      return "进行中";
    case "COMPLETED":
      return "已完成";
    case "FAILED":
      return "失败";
    case "CANCELLED":
      return "已取消";
    default:
      return status || "—";
  }
}

const BLOCKING_TASK_STATUSES = new Set(["FAILED", "WAITING_HUMAN"]);

export interface StatementBlocker {
  title: string;
  message: string;
  errorCode?: string | null;
}

/** 同一 taskType 只看最新一次，避免历史失败盖住后续成功。 */
export function resolveStatementBlocker(input: {
  stage?: string | null;
  instanceStatus?: string | null;
  lastError?: string | null;
  lastErrorCode?: string | null;
  subTasks?: Array<{
    taskType: string;
    status: string;
    title: string;
    updatedAt: string;
    lineNumber?: string | null;
  }>;
}): StatementBlocker | null {
  const stage = input.stage || "";
  const status = input.instanceStatus || "";
  if (
    status === "COMPLETED" ||
    status === "CANCELLED" ||
    stage === "STMT_SUBMITTED" ||
    stage === "STMT_CANCELLED"
  ) {
    return null;
  }

  const latestByKey = new Map<string, (typeof input.subTasks)[number]>();
  for (const task of [...(input.subTasks ?? [])].sort((left, right) =>
    left.updatedAt.localeCompare(right.updatedAt)
  )) {
    latestByKey.set(`${task.taskType}:${task.lineNumber ?? ""}`, task);
  }
  const blocking = [...latestByKey.values()]
    .filter((task) => BLOCKING_TASK_STATUSES.has(task.status))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));

  if (input.lastError && blocking.length > 0) {
    return {
      title: "当前阶段阻塞",
      message: input.lastError,
      errorCode: input.lastErrorCode,
    };
  }
  const task = blocking[0];
  if (!task) {
    return null;
  }
  return {
    title: "当前阶段阻塞",
    message:
      task.status === "WAITING_HUMAN"
        ? `${task.title}：等待人工处理`
        : `${task.title}：${task.status}`,
  };
}

export function resolvePersistedStage(
  bill: Pick<StatementBillListItem, "stage" | "checkStatus" | "invoiceStatus">
): StatementPersistedStage | string {
  if (bill.stage) return bill.stage;
  if (bill.checkStatus === "DRAFT") return "STMT_GENERATING";
  if (bill.checkStatus === "VOID") return "STMT_CANCELLED";
  if (bill.checkStatus === "CHECKED") return "STMT_SUBMITTED";
  if (bill.invoiceStatus === "UPLOADED" || bill.invoiceStatus === "REVIEWING") {
    return "STMT_PENDING_REVIEW";
  }
  return "STMT_PENDING_INVOICE";
}

export function sopProgressIndex(current: StatementSopStepId | string): number {
  const index = SOP_MAIN_STEPS.findIndex((item) => item.id === current);
  return index;
}

export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
