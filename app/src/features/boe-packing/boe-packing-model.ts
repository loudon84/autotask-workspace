import type {
  BoePackAttachment,
  BoePackAttachType,
  BoePackHeader,
  BoePackLine,
  BoePackStage,
} from "@/types/boe-packing";

export const BOE_PACK_MAIN_STAGES: BoePackStage[] = [
  "BOE_PACK_SCAN_PLAN",
  "BOE_PACK_FETCH_WMS",
  "BOE_PACK_ENRICH",
  "BOE_PACK_SAVE_DRAFT",
  "BOE_PACK_REVIEW",
  "BOE_PACK_SUBMITTING",
  "BOE_PACK_SUBMITTED",
];

export const BOE_PACK_STAGE_NAME: Record<BoePackStage, string> = {
  BOE_PACK_SCAN_PLAN: "匹配交货计划",
  BOE_PACK_FETCH_WMS: "读 WMS 装箱单",
  BOE_PACK_ENRICH: "RPA 补全项目信息行",
  BOE_PACK_SAVE_DRAFT: "保存 SRM 草稿单",
  BOE_PACK_REVIEW: "客服核验",
  BOE_PACK_SUBMITTING: "提交 SRM 单据",
  BOE_PACK_SUBMITTED: "已完成",
  BOE_PACK_CANCELLED: "已作废",
};

export const BOE_PACK_STAGE_TABS = [
  { value: "all", label: "全部" },
  { value: "BOE_PACK_FETCH_WMS", label: "读 WMS 装箱单" },
  { value: "BOE_PACK_ENRICH", label: "RPA 补全项目信息行" },
  { value: "BOE_PACK_SAVE_DRAFT", label: "保存 SRM 草稿单" },
  { value: "BOE_PACK_REVIEW", label: "客服核验" },
  { value: "BOE_PACK_SUBMITTING", label: "提交 SRM 单据" },
  { value: "BOE_PACK_SUBMITTED", label: "已完成" },
  { value: "BOE_PACK_CANCELLED", label: "已作废" },
] as const;

export const BOE_PACK_VOL_UNIT = "立方米";

export const BOE_PACK_SUBTASK_NODES = [
  { taskType: "srm_boe_pack_enrich", label: "RPA 补全项目信息行" },
  { taskType: "srm_boe_pack_save_draft", label: "保存 SRM 草稿单" },
  { taskType: "srm_boe_pack_submit", label: "提交 SRM 单据" },
];

const BOE_BLOCKING_TASK_STATUSES = new Set(["FAILED", "WAITING_HUMAN"]);

export interface BoePackBlocker {
  title: string;
  message: string;
  errorCode?: string | null;
}

/** 定位任务卡点：优先实例错误，其次最新失败的子任务。同一 taskType 只看最新一次。 */
export function resolveBoePackBlocker(input: {
  stage?: string | null;
  instanceStatus?: string | null;
  lastError?: string | null;
  lastErrorCode?: string | null;
  subTasks?: Array<{
    taskType: string;
    status: string;
    title: string;
    updatedAt: string;
  }>;
}): BoePackBlocker | null {
  const stage = input.stage || "";
  const status = input.instanceStatus || "";
  if (
    status === "COMPLETED" ||
    status === "CANCELLED" ||
    stage === "BOE_PACK_SUBMITTED" ||
    stage === "BOE_PACK_CANCELLED"
  ) {
    return null;
  }
  const stageLabel = boePackStageName(stage);
  if (input.lastError) {
    return {
      title: `卡在「${stageLabel}」`,
      message: input.lastError,
      errorCode: input.lastErrorCode,
    };
  }
  const latestByType = new Map<
    string,
    NonNullable<typeof input.subTasks>[number]
  >();
  for (const task of [...(input.subTasks ?? [])].sort((left, right) =>
    left.updatedAt.localeCompare(right.updatedAt)
  )) {
    latestByType.set(task.taskType, task);
  }
  const blocking = [...latestByType.values()]
    .filter((task) => BOE_BLOCKING_TASK_STATUSES.has(task.status))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  const task = blocking[0];
  if (!task) {
    return null;
  }
  return {
    title: `卡在「${stageLabel}」`,
    message:
      task.status === "WAITING_HUMAN"
        ? `${task.title}：等待人工处理`
        : `${task.title}：${task.status}`,
  };
}

export function boePackStageName(stage: string): string {
  return BOE_PACK_STAGE_NAME[stage as BoePackStage] ?? stage;
}

export function boePackProgressIndex(stage: string): number {
  if (stage === "BOE_PACK_CANCELLED") {
    return -1;
  }
  const index = BOE_PACK_MAIN_STAGES.indexOf(stage as BoePackStage);
  return index < 0 ? 0 : index;
}

export function canRetryBoePack(stage: string): boolean {
  return (
    stage === "BOE_PACK_FETCH_WMS" ||
    stage === "BOE_PACK_ENRICH" ||
    stage === "BOE_PACK_SAVE_DRAFT" ||
    stage === "BOE_PACK_SUBMITTING"
  );
}

export function canEditBoePack(stage: string): boolean {
  return stage === "BOE_PACK_REVIEW" || stage === "BOE_PACK_SAVE_DRAFT";
}

export function canSubmitBoePack(stage: string): boolean {
  return stage === "BOE_PACK_REVIEW";
}

const HEADER_DIFF_LABELS: Record<string, string> = {
  invoiceNo: "供应商发票号",
  factory: "BOE 工厂",
  invoiceDate: "开票日期",
  etd: "ETD",
  consignArrivalDate: "委托到货日期",
  totalVol: "总体积",
};

const LINE_DIFF_FIELDS: Array<{ key: keyof BoePackLine; label: string }> = [
  { key: "deliveryQty", label: "本次开票数" },
  { key: "netWeight", label: "净重" },
  { key: "netWeightUnit", label: "净重单位" },
  { key: "regionCode", label: "地区编号" },
  { key: "regionSrmName", label: "SRM 地区" },
  { key: "lineItem", label: "行项目" },
  { key: "orderQty", label: "订单数量" },
  { key: "orderUnit", label: "订单单位" },
  { key: "remainingQty", label: "剩余开票数" },
];

export type BoePackReviewDiff = {
  path: string;
  label: string;
  before: string;
  after: string;
};

function text(value: unknown): string {
  return String(value ?? "").trim();
}

const NUMERIC_DIFF_KEYS = new Set([
  "deliveryQty",
  "netWeight",
  "orderQty",
  "remainingQty",
  "totalVol",
]);

export function compactBoeDecimal(value: unknown, places = 5): string {
  const raw = text(value);
  if (!raw) {
    return "";
  }
  const number = Number(raw);
  if (!Number.isFinite(number)) {
    return raw;
  }
  return number.toFixed(places).replace(/\.?0+$/, "") || "0";
}

function fieldText(key: string, value: unknown): string {
  const raw = text(value);
  if (!NUMERIC_DIFF_KEYS.has(key) || !raw) {
    return raw;
  }
  if (key === "netWeight" || key === "totalVol") {
    return compactBoeDecimal(raw);
  }
  const number = Number(raw);
  if (!Number.isFinite(number)) {
    return raw;
  }
  return String(number);
}

function lineKey(line: BoePackLine): string {
  return `${text(line.poNum)}|${text(line.itemNum)}`;
}

export function boePackReviewDiffs(
  baseline: Record<string, unknown> | null | undefined,
  header: BoePackHeader,
  lines: BoePackLine[]
): BoePackReviewDiff[] {
  if (!baseline || typeof baseline !== "object") {
    return [];
  }
  const diffs: BoePackReviewDiff[] = [];
  const baseHeader =
    baseline.header && typeof baseline.header === "object"
      ? (baseline.header as Record<string, unknown>)
      : {};
  for (const [key, label] of Object.entries(HEADER_DIFF_LABELS)) {
    const before = fieldText(key, baseHeader[key]);
    const after = fieldText(key, header[key as keyof BoePackHeader]);
    if (before !== after) {
      diffs.push({ path: `header.${key}`, label, before, after });
    }
  }
  const baseLines = Array.isArray(baseline.lines)
    ? (baseline.lines as BoePackLine[])
    : [];
  const byKey = new Map(baseLines.map((line) => [lineKey(line), line]));
  const seen = new Set<string>();
  for (const line of lines) {
    const key = lineKey(line);
    seen.add(key);
    const previous = byKey.get(key);
    if (!previous) {
      diffs.push({
        path: `lines.${key}`,
        label: `新增行 ${key}`,
        before: "",
        after: text(line.deliveryQty),
      });
      continue;
    }
    for (const field of LINE_DIFF_FIELDS) {
      const before = fieldText(String(field.key), previous[field.key]);
      const after = fieldText(String(field.key), line[field.key]);
      if (before !== after) {
        diffs.push({
          path: `lines.${key}.${String(field.key)}`,
          label: `${key} ${field.label}`,
          before,
          after,
        });
      }
    }
  }
  for (const line of baseLines) {
    const key = lineKey(line);
    if (!seen.has(key)) {
      diffs.push({
        path: `lines.${key}`,
        label: `删除行 ${key}`,
        before: text(line.deliveryQty),
        after: "",
      });
    }
  }
  return diffs;
}

export const BOE_PACK_ATTACH_TYPES: BoePackAttachType[] = [
  "箱单",
  "发票",
  "提运单",
  "双签PO/协议",
];

/** SRM 默认行：箱单/发票/提运单删除 disabled，核验页也不提供删除。 */
export const BOE_PACK_FIXED_ATTACH_TYPES: ReadonlySet<string> = new Set([
  "箱单",
  "发票",
  "提运单",
]);

export function isFixedBoePackAttachment(type: string | undefined): boolean {
  const kind = text(type) === "提单" ? "提运单" : text(type);
  return BOE_PACK_FIXED_ATTACH_TYPES.has(kind);
}

const REQUIRED_HEADER: Array<{ key: keyof BoePackHeader; label: string }> = [
  { key: "invoiceNo", label: "供应商发票号" },
  { key: "factory", label: "BOE 工厂" },
  { key: "invoiceDate", label: "开票日期" },
  { key: "etd", label: "ETD" },
  { key: "consignArrivalDate", label: "委托到货日期" },
  { key: "totalVol", label: "总体积" },
];

export function boePackRequiredErrors(
  header: BoePackHeader,
  lines: BoePackLine[]
): string[] {
  const errors: string[] = [];
  for (const field of REQUIRED_HEADER) {
    if (!text(header[field.key])) {
      errors.push(`${field.label}不能为空`);
    }
  }
  if (lines.length === 0) {
    errors.push("项目信息至少一行");
    return errors;
  }
  lines.forEach((line, index) => {
    if (!text(line.deliveryQty)) {
      errors.push(`第 ${index + 1} 行本次开票数不能为空`);
    }
    if (!text(line.netWeight)) {
      errors.push(`第 ${index + 1} 行净重不能为空`);
    }
    if (!text(line.regionSrmName)) {
      errors.push(`第 ${index + 1} 行 SRM 地区不能为空`);
    }
  });
  return errors;
}

function fileStem(fileName: string): string {
  const name = text(fileName);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

export function boePackAttachmentErrors(
  invoiceNo: string,
  lines: BoePackLine[],
  attachments: BoePackAttachment[]
): string[] {
  const invoice = text(invoiceNo);
  const errors: string[] = [];
  if (!invoice) {
    errors.push("供应商发票号不能为空，无法校验附件命名");
    return errors;
  }
  const pos = [
    ...new Set(lines.map((line) => text(line.poNum)).filter(Boolean)),
  ].sort();
  const byType: Record<string, BoePackAttachment[]> = {
    箱单: [],
    发票: [],
    提运单: [],
    "双签PO/协议": [],
  };
  for (const row of attachments) {
    const kind = text(row.type) === "提单" ? "提运单" : text(row.type);
    if (!byType[kind]) {
      errors.push(`不支持的附件类型：${kind || "空"}`);
      continue;
    }
    if (!text(row.fileName)) {
      if (kind === "提运单") {
        continue;
      }
      errors.push(`${kind || "附件"}未选择文件`);
      continue;
    }
    if (!text(row.fileName).toLowerCase().endsWith(".pdf")) {
      errors.push(`${row.fileName} 必须是 PDF`);
      continue;
    }
    byType[kind].push(row);
  }
  if (byType["箱单"].length === 0) {
    errors.push("必须上传箱单");
  }
  for (const row of byType["箱单"]) {
    if (!text(row.fileName).toLowerCase().includes("pl")) {
      errors.push("箱单文件名须包含 pl（大小写均可）");
    }
  }
  if (byType["发票"].length === 0) {
    errors.push("必须上传发票");
  }
  for (const row of byType["发票"]) {
    if (fileStem(row.fileName ?? "").toLowerCase() !== invoice.toLowerCase()) {
      errors.push(`发票文件名必须是 ${invoice}.pdf`);
    }
  }
  if (byType["双签PO/协议"].length !== pos.length) {
    errors.push(`双签PO/协议须与交货明细 PO 数量一致（需要 ${pos.length} 个）`);
  }
  const covered = new Set<string>();
  for (const row of byType["双签PO/协议"]) {
    const stem = fileStem(row.fileName ?? "");
    if (!pos.includes(stem)) {
      errors.push(`双签文件名必须是采购订单号，未匹配：${row.fileName}`);
      continue;
    }
    if (covered.has(stem)) {
      errors.push(`双签 PO ${stem} 重复上传`);
      continue;
    }
    covered.add(stem);
  }
  const missing = pos.filter((po) => !covered.has(po));
  if (missing.length) {
    errors.push(`缺少双签PO：${missing.join("、")}`);
  }
  return errors;
}

export function defaultBoePackAttachments(lines: BoePackLine[]): BoePackAttachment[] {
  const pos = [...new Set(lines.map((line) => text(line.poNum)).filter(Boolean))];
  const rows: BoePackAttachment[] = [
    { id: "att-packing", type: "箱单", fileName: "", filePath: "" },
    { id: "att-invoice", type: "发票", fileName: "", filePath: "" },
    { id: "att-bl", type: "提运单", fileName: "", filePath: "" },
  ];
  if (pos.length === 0) {
    rows.push({ id: "att-dual-0", type: "双签PO/协议", fileName: "", filePath: "" });
    return rows;
  }
  pos.forEach((po, index) => {
    rows.push({
      id: `att-dual-${po}-${index}`,
      type: "双签PO/协议",
      fileName: "",
      filePath: "",
    });
  });
  return rows;
}

/** 箱单/发票/提运单永远前三行且类型锁死；后面才是双签。 */
export function normalizeBoePackAttachments(
  rows: BoePackAttachment[]
): BoePackAttachment[] {
  const byFixed: Partial<Record<"箱单" | "发票" | "提运单", BoePackAttachment>> = {};
  const dual: BoePackAttachment[] = [];
  for (const row of rows) {
    const kind = text(row.type) === "提单" ? "提运单" : text(row.type);
    if (kind === "箱单" || kind === "发票" || kind === "提运单") {
      if (!byFixed[kind]) {
        byFixed[kind] = { ...row, type: kind };
      }
    } else if (kind === "双签PO/协议") {
      dual.push({ ...row, type: "双签PO/协议" });
    }
  }
  const ids = { 箱单: "att-packing", 发票: "att-invoice", 提运单: "att-bl" } as const;
  const fixed = (["箱单", "发票", "提运单"] as const).map(
    (kind) =>
      byFixed[kind] ?? {
        id: ids[kind],
        type: kind,
        fileName: "",
        filePath: "",
      }
  );
  return [...fixed, ...dual];
}
