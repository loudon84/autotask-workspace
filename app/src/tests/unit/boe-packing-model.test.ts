import { describe, expect, it } from "vitest";
import {
  BOE_PACK_VOL_UNIT,
  boePackReviewDiffs,
  boePackStageName,
  canSubmitBoePack,
} from "@/features/boe-packing/boe-packing-model";

describe("boe packing labels", () => {
  it("uses SOP display names and submit gate", () => {
    expect(boePackStageName("BOE_PACK_FETCH_WMS")).toBe("读 WMS 装箱单");
    expect(canSubmitBoePack("BOE_PACK_REVIEW")).toBe(true);
    expect(canSubmitBoePack("BOE_PACK_SAVE_DRAFT")).toBe(false);
    expect(BOE_PACK_VOL_UNIT).toBe("立方米");
  });

  it("diffs review baseline against current header and lines", () => {
    const diffs = boePackReviewDiffs(
      {
        header: { invoiceNo: "A1", factory: "1200" },
        lines: [{ poNum: "PO1", itemNum: "M1", deliveryQty: "10" }],
      },
      { invoiceNo: "A2", factory: "1200" },
      [{ poNum: "PO1", itemNum: "M1", deliveryQty: "12" }]
    );
    expect(diffs.map((item) => item.path)).toEqual([
      "header.invoiceNo",
      "lines.PO1|M1.deliveryQty",
    ]);
  });
});
