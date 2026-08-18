export type StatementCheckStatus = "DRAFT" | "UNCHECKED" | "CHECKED" | "VOID";
export type StatementInvoiceStatus = "NOT_UPLOADED" | "UPLOADED" | "REVIEWING";
export type StatementInstanceStatus =
  | "ACTIVE"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type StatementSopStepId =
  | "STMT_CREATING"
  | "STMT_SDMS_CHECK"
  | "STMT_GENERATING"
  | "STMT_PENDING_INVOICE"
  | "STMT_PENDING_REVIEW"
  | "STMT_SUBMITTED";

export type StatementPersistedStage =
  | "STMT_GENERATING"
  | "STMT_PENDING_INVOICE"
  | "STMT_PENDING_REVIEW"
  | "STMT_SUBMITTED"
  | "STMT_CANCELLED";

export interface StatementBillListItem {
  id: string;
  processInstanceId: string;
  portalAccountId: string;
  checkDate: string;
  checkAmount: string | number;
  checkStatus: StatementCheckStatus;
  invoiceStatus: StatementInvoiceStatus;
  invoiceNo?: string | null;
  invoiceAmount?: string | number | null;
  lastError?: string | null;
  stage?: StatementPersistedStage | string | null;
  instanceStatus?: StatementInstanceStatus | string | null;
  lastErrorCode?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StatementStageHistoryItem {
  id: string;
  fromStage?: string | null;
  toStage: string;
  actor: string;
  note?: string | null;
  createdAt: string;
}

export interface StatementSubTask {
  id: string;
  title: string;
  taskType: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  lineNumber?: string | null;
}

export interface StatementBillDetail extends StatementBillListItem {
  sdmsCheckHeadId?: string | null;
  sdmsCheckNum?: string | null;
  lines?: StatementReceiptLine[];
  subTasks?: StatementSubTask[];
  stageHistory?: StatementStageHistoryItem[];
}

export interface StatementTaskResult {
  taskId: string;
  status: string;
}

export interface StatementQueryResult {
  taskId: string;
  status: string;
  runStatus?: string | null;
  rows: Record<string, unknown>[];
  errorMessage?: string | null;
}

export interface StatementGenerateResult {
  ok: boolean;
  instanceId?: string;
  taskId?: string;
  billId?: string;
  localAmount?: string;
  sdmsAmount?: string;
  sdmsCheckHeadId?: string;
  sdmsCheckNum?: string;
}

export interface StatementReceiptLine {
  receiptNo: string;
  lineNo: string;
  orderNo?: string;
  reconcileStatus?: string;
  docType?: string;
  inboundConfirmDate?: string;
  materialNumber?: string;
  itemName?: string;
  itemSpec?: string;
  receivedQty?: string;
  unitPrice?: string;
  untaxedUnitPrice?: string;
  taxRate?: string;
  untaxedAmount?: string;
  taxAmount?: string;
  taxIncludedAmount?: string;
  docDate?: string;
  billQty?: string;
  actualArrivalDate?: string;
  [key: string]: unknown;
}
