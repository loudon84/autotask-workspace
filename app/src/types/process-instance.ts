export type ProcessInstanceStatus =
  | "ACTIVE"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type ProcessStage =
  | "CREATING_SDMS"
  | "SDMS_CREATED"
  | "DATES_PARTIAL"
  | "DATES_COMPLETE"
  | "SIGN_REQUESTED"
  | "SIGNED"
  | "ARCHIVED"
  | "FAILED";

export type ProcessLineStatus =
  | "PENDING"
  | "SUBMITTING"
  | "WRITTEN"
  | "WRITE_FAILED";

export interface ProcessInstanceListItem {
  id: string;
  processCode: string;
  bizKey: string;
  title: string;
  portalAccountId: string;
  stage: ProcessStage;
  status: ProcessInstanceStatus;
  lineTotal: number;
  lineDone: number;
  lastErrorCode?: string | null;
  lastErrorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProcessLineItem {
  id: string;
  lineNumber: string;
  materialNumber: string;
  itemName?: string | null;
  itemSpecification?: string | null;
  materialStatus?: string | null;
  internalCode?: string | null;
  orderQuantity?: string | null;
  orderQuantityUom?: string | null;
  unitSellingPrice?: string | null;
  taxIncludedAmount?: string | null;
  requestDate?: string | null;
  standardDeliveryDays?: string | null;
  meetsLeadTime?: string | null;
  supplierDeliveryDate?: string | null;
  outstandingQuantity?: string | null;
  remarks?: string | null;
  directShipmentRemarks?: string | null;
  expectedDeliveryDate?: string | null;
  lineStatus: ProcessLineStatus;
  subTaskId?: string | null;
  lastErrorCode?: string | null;
  lastErrorMessage?: string | null;
}

export interface ProcessStageHistoryItem {
  id: string;
  fromStage?: string | null;
  toStage: string;
  actor: string;
  note?: string | null;
  createdAt: string;
}

export interface ProcessSubTask {
  id: string;
  title: string;
  taskType: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  lineNumber?: string | null;
}

export interface ProcessInstanceDetail extends ProcessInstanceListItem {
  summary: Record<string, unknown>;
  lines: ProcessLineItem[];
  stageHistory: ProcessStageHistoryItem[];
  subTasks: ProcessSubTask[];
}

export interface ProcessScanResult {
  taskId: string;
  status: string;
}

export interface ProcessSignPollRunResult {
  candidateCount: number;
  createdCount: number;
}
