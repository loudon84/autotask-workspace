export const DELIVERY_DATE_TASK_TYPE = "srm_update_expected_delivery_dates";
const CANONICAL_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export interface DeliveryDateLine {
  expectedDeliveryDate: string;
  itemName: string;
  itemSpecification: string;
  lineNumber: string;
  materialNumber: string;
  orderQuantity: string;
  orderQuantityUom: string;
  raw: Record<string, unknown>;
  requestDate: string;
  standardDeliveryDays: string;
}

export interface ManualDeliveryDateLineInput {
  lineNumber: string;
  materialNumber: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

export function displayTaskValue(value: unknown): string {
  return text(value).trim() || "—";
}

export function parseDeliveryDateLines(
  input: Record<string, unknown>
): DeliveryDateLine[] {
  const rawLines = input.order_lines;
  if (!Array.isArray(rawLines)) {
    return [];
  }
  return rawLines.map((value) => {
    const raw = isRecord(value) ? value : {};
    return {
      expectedDeliveryDate: text(raw.expected_delivery_date),
      itemName: text(raw.item_name),
      itemSpecification: text(raw.item_specification),
      lineNumber: text(raw.line_number),
      materialNumber: text(raw.material_number),
      orderQuantity: text(raw.order_quantity),
      orderQuantityUom: text(raw.order_quantity_uom),
      raw,
      requestDate: text(raw.request_date),
      standardDeliveryDays: text(raw.standard_delivery_days),
    };
  });
}

export function isCanonicalDate(value: string): boolean {
  const match = CANONICAL_DATE_PATTERN.exec(value);
  if (!match) {
    return false;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

export function isDeliveryDateInputComplete(
  input: Record<string, unknown>
): boolean {
  const lines = parseDeliveryDateLines(input);
  if (lines.length === 0) {
    return false;
  }
  const seen = new Set<string>();
  return lines.every((line) => {
    if (
      !(line.lineNumber && line.materialNumber) ||
      seen.has(line.lineNumber) ||
      !isCanonicalDate(line.expectedDeliveryDate)
    ) {
      return false;
    }
    seen.add(line.lineNumber);
    return true;
  });
}

export function deliveryDateSignature(lines: DeliveryDateLine[]): string {
  return JSON.stringify(lines.map((line) => line.expectedDeliveryDate));
}

export function validateManualDeliveryDateLines(
  lines: ManualDeliveryDateLineInput[]
): string | null {
  if (lines.length === 0) {
    return "请至少添加一条订单明细";
  }
  const seen = new Set<string>();
  for (const [index, line] of lines.entries()) {
    const lineNumber = line.lineNumber.trim();
    const materialNumber = line.materialNumber.trim();
    if (!(lineNumber && materialNumber)) {
      return `第 ${index + 1} 条明细必须填写行号和物料号`;
    }
    if (seen.has(lineNumber)) {
      return `订单行号 ${lineNumber} 重复`;
    }
    seen.add(lineNumber);
  }
  return null;
}

export function serializeManualDeliveryDateLines(
  lines: ManualDeliveryDateLineInput[]
): Record<string, unknown>[] {
  return lines.map((line) => ({
    expected_delivery_date: null,
    line_number: line.lineNumber.trim(),
    material_number: line.materialNumber.trim(),
  }));
}
