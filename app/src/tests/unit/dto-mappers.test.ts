import { describe, expect, it } from "vitest";
import {
  mapItemResponse,
  mapKeysToCamel,
  mapListResponse,
} from "@/services/dto-mappers";

describe("dto-mappers", () => {
  it("maps snake_case keys to camelCase", () => {
    const result = mapKeysToCamel<{ taskId: string; customerName: string }>({
      task_id: "t1",
      customer_name: "Acme",
    });
    expect(result).toEqual({ taskId: "t1", customerName: "Acme" });
  });

  it("maps list response from items array", () => {
    const result = mapListResponse<{ id: string }>({
      items: [{ id: "1" }, { id: "2" }],
    });
    expect(result).toHaveLength(2);
    expect(result[0]?.id).toBe("1");
  });

  it("unwraps envelope for list response", () => {
    const result = mapListResponse<{ id: string }>({
      code: 0,
      message: "success",
      data: [{ id: "1" }],
    });
    expect(result).toHaveLength(1);
    expect(result[0]?.id).toBe("1");
  });

  it("throws when envelope code is not 0", () => {
    expect(() =>
      mapListResponse<{ id: string }>({
        code: 1,
        message: "failed",
        data: [],
      })
    ).toThrow("failed");
  });

  it("unwraps envelope with nested items", () => {
    const result = mapListResponse<{ id: string }>({
      code: 0,
      message: "success",
      data: { items: [{ id: "1" }, { id: "2" }] },
    });
    expect(result).toHaveLength(2);
  });

  it("returns empty array when envelope data is not a list", () => {
    const result = mapListResponse<{ id: string }>({
      code: 0,
      message: "success",
      data: { today_total: 0 },
    });
    expect(result).toEqual([]);
  });

  it("maps single item response", () => {
    const result = mapItemResponse<{ status: string }>({
      status: "READY",
    });
    expect(result.status).toBe("READY");
  });

  it("unwraps envelope for single item response", () => {
    const result = mapItemResponse<{ ready: number }>({
      code: 0,
      message: "success",
      data: { ready: 3 },
    });
    expect(result.ready).toBe(3);
  });

  it("preserves workflow business input keys", () => {
    const result = mapItemResponse<{
      input: Record<string, unknown>;
      taskType: string;
    }>({
      task_type: "srm_update_expected_delivery_dates",
      input: {
        po_no: "PO-001",
        order_lines: [
          {
            line_number: "10",
            material_number: "MAT-001",
          },
        ],
      },
    });

    expect(result.taskType).toBe("srm_update_expected_delivery_dates");
    expect(result.input).toEqual({
      po_no: "PO-001",
      order_lines: [
        {
          line_number: "10",
          material_number: "MAT-001",
        },
      ],
    });
  });
});
