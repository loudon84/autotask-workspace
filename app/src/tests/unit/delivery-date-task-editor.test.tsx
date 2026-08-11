import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeliveryDateTaskEditor } from "@/features/tasks/delivery-date-task-editor";
import {
  isCanonicalDate,
  isDeliveryDateInputComplete,
  serializeManualDeliveryDateLines,
  validateManualDeliveryDateLines,
} from "@/features/tasks/delivery-date-task-model";

const { updateTaskMock } = vi.hoisted(() => ({
  updateTaskMock: vi.fn(),
}));
const WRONG_ORDER_LINES_PATTERN = /当前 order_lines 类型错误/;
const RECREATE_TASK_PATTERN = /使用新版明细表重新创建/;

vi.mock("@/services/autotask-api", () => ({
  autotaskApi: {
    tasks: {
      update: updateTaskMock,
    },
  },
}));

const input = {
  po_no: "PO-001",
  order_number: "ERP-001",
  supplier_code: "SUP-001",
  supplier_name: "测试供应商",
  source_task_id: "task-source",
  order_lines: [
    {
      line_number: "10",
      material_number: "MAT-001",
      item_name: "物料 A",
      item_specification: "规格 A",
      order_quantity: "2",
      order_quantity_uom: "EA",
      request_date: "2026-08-01",
      standard_delivery_days: "7",
      expected_delivery_date: null,
    },
    {
      line_number: "20",
      material_number: "MAT-002",
      item_name: "物料 B",
      order_quantity: "3",
      order_quantity_uom: "EA",
      expected_delivery_date: null,
    },
  ],
};

describe("DeliveryDateTaskEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateTaskMock.mockResolvedValue({ id: "task-2" });
  });

  it("renders order lines and saves edited dates without dropping fields", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    render(
      <DeliveryDateTaskEditor
        input={input}
        onSaved={onSaved}
        status="DRAFT"
        taskId="task-2"
      />
    );

    expect(screen.getByText("采购订单：PO-001")).toBeInTheDocument();
    expect(screen.getByText("MAT-001")).toBeInTheDocument();
    expect(screen.getByText("已填写 0/2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存交货日期" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("第 10 行预计交货日期"), {
      target: { value: "2026-08-10" },
    });
    fireEvent.change(screen.getByLabelText("第 20 行预计交货日期"), {
      target: { value: "2026-08-12" },
    });
    await user.click(screen.getByRole("button", { name: "保存交货日期" }));

    await waitFor(() => expect(updateTaskMock).toHaveBeenCalledOnce());
    const patch = updateTaskMock.mock.calls[0][1];
    expect(patch.input.source_task_id).toBe("task-source");
    expect(patch.input.order_lines).toEqual([
      expect.objectContaining({
        expected_delivery_date: "2026-08-10",
        line_number: "10",
        material_number: "MAT-001",
      }),
      expect.objectContaining({
        expected_delivery_date: "2026-08-12",
        line_number: "20",
        material_number: "MAT-002",
      }),
    ]);
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("allows a partial draft to be saved", async () => {
    const user = userEvent.setup();
    render(
      <DeliveryDateTaskEditor input={input} status="READY" taskId="task-2" />
    );

    fireEvent.change(screen.getByLabelText("第 10 行预计交货日期"), {
      target: { value: "2026-08-10" },
    });
    await user.click(screen.getByRole("button", { name: "保存交货日期" }));

    await waitFor(() => expect(updateTaskMock).toHaveBeenCalledOnce());
    expect(updateTaskMock.mock.calls[0][1].input.order_lines[1]).toHaveProperty(
      "expected_delivery_date",
      null
    );
  });

  it("is read-only after the task enters the queue", () => {
    render(
      <DeliveryDateTaskEditor
        input={{
          ...input,
          order_lines: input.order_lines.map((line) => ({
            ...line,
            expected_delivery_date: "2026-08-10",
          })),
        }}
        status="QUEUED"
        taskId="task-2"
      />
    );

    expect(
      screen.queryByRole("button", { name: "保存交货日期" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("第 10 行预计交货日期")
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("任务进入队列后，输入参数不可再修改。")
    ).toBeInTheDocument();
  });

  it("explains how to replace a task created with a string order_lines", () => {
    render(
      <DeliveryDateTaskEditor
        input={{ po_no: "PO-001", order_lines: "10" }}
        status="DRAFT"
        taskId="task-2"
      />
    );

    expect(screen.getByText(WRONG_ORDER_LINES_PATTERN)).toBeInTheDocument();
    expect(screen.getByText(RECREATE_TASK_PATTERN)).toBeInTheDocument();
  });
});

describe("delivery date validation", () => {
  it("accepts only real canonical calendar dates", () => {
    expect(isCanonicalDate("2026-02-28")).toBe(true);
    expect(isCanonicalDate("2026-02-30")).toBe(false);
    expect(isCanonicalDate("2026-2-8")).toBe(false);
  });

  it("requires unique lines, material numbers and every date", () => {
    const complete = {
      ...input,
      order_lines: input.order_lines.map((line, index) => ({
        ...line,
        expected_delivery_date: `2026-08-${10 + index}`,
      })),
    };
    expect(isDeliveryDateInputComplete(complete)).toBe(true);
    expect(isDeliveryDateInputComplete(input)).toBe(false);
    expect(
      isDeliveryDateInputComplete({
        ...complete,
        order_lines: complete.order_lines.map((line) => ({
          ...line,
          line_number: "10",
        })),
      })
    ).toBe(false);
  });

  it("validates and serializes manually entered order lines", () => {
    const lines = [
      { lineNumber: " 10 ", materialNumber: " MAT-001 " },
      { lineNumber: "20", materialNumber: "MAT-002" },
    ];
    expect(validateManualDeliveryDateLines(lines)).toBeNull();
    expect(serializeManualDeliveryDateLines(lines)).toEqual([
      {
        expected_delivery_date: null,
        line_number: "10",
        material_number: "MAT-001",
      },
      {
        expected_delivery_date: null,
        line_number: "20",
        material_number: "MAT-002",
      },
    ]);
    expect(
      validateManualDeliveryDateLines([
        { lineNumber: "10", materialNumber: "MAT-001" },
        { lineNumber: "10", materialNumber: "MAT-002" },
      ])
    ).toBe("订单行号 10 重复");
  });
});
