import { describe, expect, it } from "vitest";
import {
  isStatementAmountMismatchError,
  resolveStatementBlocker,
} from "@/features/statements/statement-model";

describe("resolveStatementBlocker", () => {
  it("hides a historical generate failure after a later generate succeeded", () => {
    const blocker = resolveStatementBlocker({
      stage: "STMT_PENDING_INVOICE",
      instanceStatus: "ACTIVE",
      lastError: null,
      subTasks: [
        {
          taskType: "srm_stmt_generate",
          status: "FAILED",
          title: "对账单：重新生成对账单",
          updatedAt: "2026-08-18T03:57:00Z",
        },
        {
          taskType: "srm_stmt_generate",
          status: "SUCCESS",
          title: "对账单：重新生成对账单",
          updatedAt: "2026-08-18T04:03:00Z",
        },
      ],
    });
    expect(blocker).toBeNull();
  });

  it("still shows the latest generate failure", () => {
    const blocker = resolveStatementBlocker({
      stage: "STMT_GENERATING",
      instanceStatus: "ACTIVE",
      lastError: "receipt row checkbox is not clickable",
      lastErrorCode: "SRM_STMT_ROW_CHECKBOX_UNCLICKABLE",
      subTasks: [
        {
          taskType: "srm_stmt_generate",
          status: "FAILED",
          title: "对账单：重新生成对账单",
          updatedAt: "2026-08-18T03:57:00Z",
        },
      ],
    });
    expect(blocker?.message).toBe("receipt row checkbox is not clickable");
  });
});

describe("isStatementAmountMismatchError", () => {
  it("detects the Task message key", () => {
    expect(
      isStatementAmountMismatchError({
        message: "冲突",
        body: { message_key: "errors.autotask.statement.amount_mismatch" },
      })
    ).toBe(true);
  });

  it("detects the Chinese amount mismatch message", () => {
    expect(
      isStatementAmountMismatchError(
        new Error("对账金额不一致：SDMS 1 vs 勾选汇总 2，确认后仍可继续生成")
      )
    ).toBe(true);
  });

  it("ignores other conflicts", () => {
    expect(
      isStatementAmountMismatchError(
        new Error("当天已存在相同金额的对账单")
      )
    ).toBe(false);
  });
});
