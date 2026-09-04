export type BoePackStage =
  | "BOE_PACK_SCAN_PLAN"
  | "BOE_PACK_FETCH_WMS"
  | "BOE_PACK_ENRICH"
  | "BOE_PACK_SAVE_DRAFT"
  | "BOE_PACK_REVIEW"
  | "BOE_PACK_SUBMITTING"
  | "BOE_PACK_SUBMITTED"
  | "BOE_PACK_CANCELLED";

export type BoePackHeader = {
  aiRecognize?: boolean;
  invoiceNo?: string;
  factory?: string;
  customerName?: string;
  customerSubcode?: string;
  businessEntity?: string;
  invoiceDate?: string;
  etd?: string;
  consignArrivalDate?: string;
  totalVol?: string;
  volUnit?: string;
};

export type BoePackLine = {
  lineNo?: string;
  poNum?: string;
  itemNum?: string;
  deliveryQty?: string;
  netWeight?: string;
  regionCode?: string;
  regionSrmName?: string;
  lineItem?: string;
  remainingQty?: string;
  itemName?: string;
  factory?: string;
};

export type BoePackListItem = {
  id: string;
  processCode: string;
  bizKey: string;
  title: string;
  portalAccountId: string;
  stage: BoePackStage;
  status: string;
  lineTotal: number;
  lineDone: number;
  lastErrorCode?: string | null;
  lastErrorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  qtyMismatch?: boolean;
  invoiceNo?: string;
  factory?: string;
  customerName?: string;
};

export type BoePackDetail = BoePackListItem & {
  header: BoePackHeader;
  lines: BoePackLine[];
  qtyWarning?: string | null;
  orgCodeWarning?: string | null;
  srmDraftNo?: string;
  reviewBaseline?: Record<string, unknown> | null;
  stageHistory: Array<{
    id: string;
    fromStage?: string | null;
    toStage: string;
    actor: string;
    note?: string | null;
    createdAt: string;
  }>;
  subTasks: Array<{
    id: string;
    title: string;
    taskType: string;
    status: string;
    createdAt: string;
    updatedAt: string;
  }>;
};

export type BoeMatchResult = {
  createdCount: number;
  skippedCount: number;
  missingPortal: string[];
  error?: string | null;
  createdIds: string[];
};
