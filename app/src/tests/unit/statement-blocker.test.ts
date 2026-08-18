import { describe, expect, it } from "vitest";
import { resolveStatementBlocker } from "@/features/statements/statement-model";

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
