import { describe, expect, it } from "vitest";
import {
  mapRemoteBinding,
  mapRemotePortal,
  mapRemoteTask,
  mapRemoteWorkflow,
  toRemoteBindingCreate,
  toRemoteBindingUpdate,
  toRemotePortalCreate,
  toRemotePortalUpdate,
  toRemoteTaskCreate,
  toRemoteWorkflowCreate,
  toRemoteWorkflowUpdate,
} from "@/services/remote-dto-mappers";

describe("remote DTO 映射", () => {
  it("将 PortalAccountResponse 映射为 Client Portal", () => {
    const portal = mapRemotePortal({
      id: "portal-1",
      entityType: "CUSTOMER",
      erpEntityCode: "C001",
      erpEntityName: "客户一",
      portalName: "供应商门户",
      portalUrl: "http://localhost:3000",
      loginAccount: "demo",
      clientOpenMode: "webcontents",
      clientSessionPartition: "persist:portal-1",
      status: "ENABLED",
      createdAt: "2026-07-27T00:00:00Z",
      updatedAt: "2026-07-27T00:00:00Z",
    });

    expect(portal).toMatchObject({
      id: "portal-1",
      entityType: "CUSTOMER",
      erpEntityCode: "C001",
      customerName: "客户一",
      name: "供应商门户",
      status: "enabled",
      url: "http://localhost:3000",
    });
  });

  it("将模板状态、输入字段和业务步骤映射为 Client 模型", () => {
    const workflow = mapRemoteWorkflow({
      id: "workflow-1",
      name: "拉取 PO",
      code: "srm_fetch_po",
      description: null,
      category: "procurement",
      status: "ENABLED",
      version: "1.0.0",
      inputSchema: [{ name: "po_no", type: "string", required: true }],
      businessSteps: [{ id: "login", name: "登录", type: "browser.login" }],
      createdAt: "2026-07-27T00:00:00Z",
      updatedAt: "2026-07-27T00:00:00Z",
    });

    expect(workflow.status).toBe("enabled");
    expect(workflow.entityType).toBeUndefined();
    expect(workflow.inputSchema).toEqual([
      { name: "po_no", label: "po_no", type: "string", required: true },
    ]);
    expect(workflow.steps[0]).toMatchObject({
      id: "login",
      name: "登录",
      type: "browser.login",
    });
  });

  it("保留精确 Binding 快照", () => {
    const binding = mapRemoteBinding({
      id: "binding-1",
      portalAccountId: "portal-1",
      workflowTemplateId: "workflow-1",
      workflowTemplateVersion: "1.0.0",
      rpaEngineType: "PLAYWRIGHT_CDP",
      rpaFlowId: "rpa_flow_srm_fetch_po",
      rpaFlowVersion: "1.1.0",
      rpaFlowVersionId: "version-1",
      flowChecksumSnapshot: "checksum-1",
      status: "ENABLED",
      config: { browserSession: { mode: "MANAGED" } },
      createdAt: "2026-07-27T00:00:00Z",
      updatedAt: "2026-07-27T00:00:00Z",
    });

    expect(binding).toMatchObject({
      id: "binding-1",
      rpaFlowVersionId: "version-1",
      flowChecksumSnapshot: "checksum-1",
      status: "enabled",
    });
  });

  it("兼容任务详情 DTO 并规范化优先级", () => {
    const task = mapRemoteTask({
      id: "task-1",
      title: "演示任务",
      taskType: "srm_fetch_po",
      portalAccountId: "portal-1",
      workflowBindingId: "binding-1",
      entityType: "CUSTOMER",
      erpEntityCode: "C001",
      erpEntityName: "客户一",
      status: "READY",
      priority: "NORMAL",
      input: { po_no: "PO-001" },
      progress: 0,
      createdBy: "user-1",
      createdAt: "2026-07-27T00:00:00Z",
      updatedAt: "2026-07-27T00:00:00Z",
    });

    expect(task).toMatchObject({
      portalId: "portal-1",
      workflowBindingId: "binding-1",
      customerName: "客户一",
      owner: "user-1",
      priority: "normal",
    });
  });

  it("创建任务时只发送 Task 要求的 snake_case 字段", () => {
    const payload = toRemoteTaskCreate({
      title: "演示任务",
      taskType: "srm_fetch_po",
      portalAccountId: "portal-1",
      workflowBindingId: "binding-1",
      entityType: "CUSTOMER",
      erpEntityCode: "C001",
      erpEntityName: "客户一",
      priority: "normal",
      input: { po_no: "PO-001" },
    });

    expect(payload).toEqual({
      title: "演示任务",
      task_type: "srm_fetch_po",
      portal_account_id: "portal-1",
      workflow_binding_id: "binding-1",
      entity_type: "CUSTOMER",
      erp_entity_code: "C001",
      erp_entity_name: "客户一",
      priority: "NORMAL",
      input: { po_no: "PO-001" },
    });
  });

  it("按 Task 契约区分 Portal camelCase 与模板 snake_case", () => {
    expect(
      toRemotePortalCreate({
        entityType: "CUSTOMER",
        erpEntityCode: "C001",
        erpEntityName: "客户一",
        businessEntity: "深圳市芯云信息科技有限公司",
        ou: "104",
        category: "TIANDI",
        portalName: "供应商门户",
        portalUrl: "https://supplier.example.com",
        loginAccount: "demo",
        credentialRef: "credential-demo",
        clientOpenMode: "webcontents",
        clientSessionPartition: "persist:srm:demo",
        status: "enabled",
        ownerUserId: "admin",
        ownerName: "admin",
        createdByName: "admin",
      })
    ).toMatchObject({
      entityType: "CUSTOMER",
      erpEntityCode: "C001",
      businessEntity: "深圳市芯云信息科技有限公司",
      ou: "104",
      category: "TIANDI",
      credentialRef: "credential-demo",
      status: "ENABLED",
    });

    expect(
      toRemoteWorkflowCreate({
        name: "拉取 PO",
        code: "srm_fetch_po",
        entityType: "CUSTOMER",
        category: "procurement",
        status: "draft",
        version: "1.0.0",
        inputSchema: [],
        businessSteps: [],
      })
    ).toMatchObject({
      entity_type: "CUSTOMER",
      input_schema: [],
      business_steps: [],
      status: "DRAFT",
    });
  });

  it("更新时省略未填写字段，并且不清空 credentialRef", () => {
    expect(
      toRemotePortalUpdate({
        portalName: "新名称",
        credentialRef: "",
      })
    ).toEqual({ portalName: "新名称" });
    expect(toRemoteWorkflowUpdate({ version: "1.1.0" })).toEqual({
      version: "1.1.0",
    });
  });

  it("创建和更新 Binding 时发送精确 Flow 版本字段", () => {
    const createPayload = toRemoteBindingCreate({
      portalAccountId: "portal-1",
      workflowTemplateId: "workflow-1",
      workflowTemplateVersion: "1.0.0",
      rpaEngineType: "PLAYWRIGHT_CDP",
      rpaFlowId: "rpa_flow_srm_fetch_po",
      rpaFlowVersion: "1.1.0",
      status: "enabled",
      config: { browserSession: { mode: "MANAGED" } },
    });
    expect(createPayload).toMatchObject({
      portal_account_id: "portal-1",
      workflow_template_id: "workflow-1",
      rpa_flow_version: "1.1.0",
      status: "ENABLED",
    });

    expect(
      toRemoteBindingUpdate({
        rpaFlowVersion: "1.2.0",
        status: "disabled",
      })
    ).toEqual({
      rpa_flow_version: "1.2.0",
      status: "DISABLED",
    });
  });
});
