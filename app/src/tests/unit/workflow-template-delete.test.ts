import { describe, expect, it } from "vitest";
import { ApiClientError } from "@/actions/autotask-api";
import { getWorkflowDeleteErrorMessage } from "@/features/workflows/api/use-workflow-templates";

describe("getWorkflowDeleteErrorMessage", () => {
  it("明确提示模板已被 Binding 引用", () => {
    const error = new ApiClientError("资源冲突", 409, {
      message_key: "errors.autotask.workflow_delete_binding_referenced",
    });

    expect(getWorkflowDeleteErrorMessage(error)).toBe(
      "模板已被 Binding 引用，只能禁用"
    );
  });

  it("明确提示模板已被历史任务引用", () => {
    const error = new ApiClientError("资源冲突", 409, {
      message_key: "errors.autotask.workflow_delete_task_referenced",
    });

    expect(getWorkflowDeleteErrorMessage(error)).toBe(
      "模板已被历史任务引用，只能禁用"
    );
  });

  it("明确提示启用中的模板需要先禁用", () => {
    const error = new ApiClientError("资源冲突", 409, {
      message_key: "errors.autotask.workflow_delete_requires_disabled",
    });

    expect(getWorkflowDeleteErrorMessage(error)).toBe(
      "启用中的模板不能删除，请先禁用"
    );
  });
});
