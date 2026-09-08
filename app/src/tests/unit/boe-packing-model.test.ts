import { describe, expect, it } from "vitest";
import {
  BOE_PACK_VOL_UNIT,
  boePackAttachmentErrors,
  boePackRequiredErrors,
  boePackReviewDiffs,
  boePackStageName,
  canSubmitBoePack,
  defaultBoePackAttachments,
  compactBoeDecimal,
  isFixedBoePackAttachment,
  normalizeBoePackAttachments,
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
    expect(
      boePackReviewDiffs(
        {
          header: { totalVol: "0.06534" },
          lines: [{ poNum: "PO1", itemNum: "M1", netWeight: "3.521" }],
        },
        { totalVol: "0.06534000" },
        [{ poNum: "PO1", itemNum: "M1", netWeight: "3.52100000000000000" }]
      )
    ).toEqual([]);
  });

  it("requires review fields and attachment naming rules", () => {
    const header = {
      invoiceNo: "101SJH202609195",
      factory: "1200",
      invoiceDate: "2026-09-07",
      etd: "2026-09-07",
      consignArrivalDate: "2026-09-12",
      totalVol: "0.06",
    };
    const lines = [
      {
        poNum: "9100069442",
        deliveryQty: "10",
        netWeight: "1",
        regionSrmName: "中国台湾",
      },
    ];
    expect(boePackRequiredErrors(header, lines)).toEqual([]);
    expect(boePackRequiredErrors({ ...header, factory: "" }, lines).length).toBeGreaterThan(0);
    expect(
      boePackAttachmentErrors(header.invoiceNo, lines, [
        { type: "箱单", fileName: "PL-101SJH202609195.pdf" },
        { type: "发票", fileName: "101SJH202609195.pdf" },
        { type: "提运单", fileName: "bl.pdf" },
        { type: "双签PO/协议", fileName: "9100069442.pdf" },
      ])
    ).toEqual([]);
    expect(
      boePackAttachmentErrors(header.invoiceNo, lines, [
        { type: "箱单", fileName: "pl_box.pdf" },
        { type: "发票", fileName: "101SJH202609195.pdf" },
        { type: "双签PO/协议", fileName: "9100069442.pdf" },
      ])
    ).toEqual([]);
    expect(
      boePackAttachmentErrors(header.invoiceNo, lines, [
        { type: "箱单", fileName: "wrong.pdf" },
      ]).length
    ).toBeGreaterThan(0);
    expect(isFixedBoePackAttachment("箱单")).toBe(true);
    expect(isFixedBoePackAttachment("发票")).toBe(true);
    expect(isFixedBoePackAttachment("提运单")).toBe(true);
    expect(isFixedBoePackAttachment("提单")).toBe(true);
    expect(isFixedBoePackAttachment("双签PO/协议")).toBe(false);
  });

  it("compacts net weight and volume to 5 decimal places", () => {
    expect(compactBoeDecimal("0.45000")).toBe("0.45");
    expect(compactBoeDecimal("3.52100000000000000")).toBe("3.521");
    expect(compactBoeDecimal("0.06534")).toBe("0.06534");
    expect(compactBoeDecimal("0.02000000")).toBe("0.02");
  });

  it("keeps packing/invoice/bl first then dual-sign rows", () => {
    expect(
      defaultBoePackAttachments([
        { poNum: "P1" },
        { poNum: "P1" },
        { poNum: "P2" },
      ]).map((row) => row.type)
    ).toEqual(["箱单", "发票", "提运单", "双签PO/协议", "双签PO/协议"]);
    expect(
      normalizeBoePackAttachments([
        { id: "d", type: "双签PO/协议", fileName: "P1.pdf", filePath: "a" },
        { id: "i", type: "发票", fileName: "inv.pdf", filePath: "b" },
        { id: "p", type: "箱单", fileName: "pl.pdf", filePath: "c" },
      ]).map((row) => row.type)
    ).toEqual(["箱单", "发票", "提运单", "双签PO/协议"]);
  });
});
