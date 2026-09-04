import type { BoePackHeader, BoePackLine, BoePackStage } from "@/types/boe-packing";

export const BOE_PACK_MAIN_STAGES: BoePackStage[] = [
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

export function boePackStageName(stage: string): string {
  return BOE_PACK_STAGE_NAME[stage as BoePackStage] ?? stage;
}

export function boePackProgressIndex(stage: string): number {
  if (stage === "BOE_PACK_SCAN_PLAN") {
    return 0;
  }
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
  { key: "regionCode", label: "地区编号" },
  { key: "regionSrmName", label: "SRM 地区" },
  { key: "lineItem", label: "行项目" },
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
    const before = text(baseHeader[key]);
    const after = text(header[key as keyof BoePackHeader]);
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
      const before = text(previous[field.key]);
      const after = text(line[field.key]);
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
