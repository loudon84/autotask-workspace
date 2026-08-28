import artifactsData from "@/mock/artifacts.json";
import auditLogsData from "@/mock/audit-logs.json";
import dashboardData from "@/mock/dashboard.json";
import rpaComponentsData from "@/mock/rpa-components.json";
import srmPortalsData from "@/mock/srm-portals.json";
import taskRunsData from "@/mock/task-runs.json";
import tasksData from "@/mock/tasks.json";
import workersData from "@/mock/workers.json";
import workflowTemplatesData from "@/mock/workflow-templates.json";
import { mapPortalAccount } from "@/services/dto-mappers";
import {
  getHumanActionById,
  getHumanActionByTaskId,
  getHumanActionsFromStore,
  useHumanActionStore,
} from "@/stores/human-action-store";
import { useSettingsStore } from "@/stores/settings-store";
import { mergeTasks, useTaskStore } from "@/stores/task-store";
import type { Artifact } from "@/types/artifact";
import type { AuditLog } from "@/types/audit-log";
import type {
  AutomationTask,
  AutomationTaskStatus,
  CreateAutomationTaskInput,
} from "@/types/automation-task";
import type { DashboardData } from "@/types/dashboard";
import type { HumanAction } from "@/types/human-action";
import type { IntegrationCallLog } from "@/types/integration-call-log";
import type { IntegrationEndpoints } from "@/types/integration-endpoints";
import type {
  CreatePortalAccountInput,
  PortalAccount,
  UpdatePortalAccountInput,
} from "@/types/portal-account";
import type { RpaComponent } from "@/types/rpa-component";
import type { AppSettings } from "@/types/settings";
import type { TaskRun } from "@/types/task-run";
import type { Worker } from "@/types/worker";
import type {
  CreateWorkflowTemplateInput,
  UpdateWorkflowTemplateInput,
  WorkflowTemplate,
} from "@/types/workflow";
import type {
  CreateWorkflowBindingInput,
  UpdateWorkflowBindingInput,
  WorkflowBinding,
  WorkflowBindingStatus,
} from "@/types/workflow-binding";

const addedWorkflows: WorkflowTemplate[] = [];
const workflowOverrides = new Map<string, Partial<WorkflowTemplate>>();
const deletedWorkflowIds = new Set<string>();
const addedBindings: WorkflowBinding[] = [];
const bindingOverrides = new Map<string, Partial<WorkflowBinding>>();

function getDelay(): number {
  return useSettingsStore.getState().settings.mockDelayMs;
}

async function delay<T>(data: T): Promise<T> {
  const ms = getDelay();
  if (ms > 0) {
    await new Promise((resolve) => setTimeout(resolve, ms));
  }
  return data;
}

function getTasks(): AutomationTask[] {
  const { addedTasks, overrides } = useTaskStore.getState();
  return mergeTasks(tasksData as AutomationTask[], addedTasks, overrides);
}

function now() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

function newId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const mockSchedulerJobs = [
  {
    id: "job-scan-1",
    bindingId: "binding-scan-1",
    portalAccountId: "portal-1",
    portalName: "天地伟业",
    name: "天地伟业-客户订单-扫单",
    cron: "0 8 * * *",
    enabled: true,
    nextRunAt: "2026-08-25T00:00:00+08:00",
  },
  {
    id: "job-sign-1",
    bindingId: "binding-sign-1",
    portalAccountId: "portal-1",
    portalName: "天地伟业",
    name: "天地伟业-客户订单-回签轮询",
    cron: "*/30 * * * *",
    enabled: false,
    nextRunAt: null,
  },
];

const mockSchedulerJobTasks = [
  {
    jobId: "job-scan-1",
    id: "task-scan-1",
    title: "扫单：SRM 待签章订单",
    status: "SUCCESS",
    createdAt: "2026-08-24T08:00:00+08:00",
  },
];

function getPortals(): PortalAccount[] {
  return mockPortalStore.map((portal) => mapPortalAccount(portal));
}

const mockPortalStore: PortalAccount[] = (
  srmPortalsData as unknown as Record<string, unknown>[]
).map((item) => mapPortalAccount(item));

function findPortalById(portalId: string): PortalAccount | undefined {
  return getPortals().find((p) => p.id === portalId);
}

function getWorkflows(): WorkflowTemplate[] {
  return [...(workflowTemplatesData as WorkflowTemplate[]), ...addedWorkflows]
    .filter((workflow) => !deletedWorkflowIds.has(workflow.id))
    .map((workflow) => ({
      ...workflow,
      entityType: workflow.entityType ?? "CUSTOMER",
      ...workflowOverrides.get(workflow.id),
    }));
}

function getWorkflowBindings(): WorkflowBinding[] {
  const portals = getPortals().filter((portal) => portal.status === "ENABLED");
  const workflows = getWorkflows().filter(
    (workflow) => workflow.status === "enabled"
  );
  const derivedBindings = portals.flatMap((portal) =>
    workflows.map<WorkflowBinding>((workflow) => ({
      id: `binding_${portal.id}_${workflow.id}`,
      portalAccountId: portal.id,
      workflowTemplateId: workflow.id,
      workflowTemplateVersion: workflow.version,
      rpaEngineType: "PLAYWRIGHT_CDP",
      rpaFlowId: `rpa_flow_${workflow.code}`,
      rpaFlowVersion: workflow.version,
      rpaFlowVersionId: `mock_version_${portal.id}_${workflow.id}`,
      flowChecksumSnapshot: `mock_checksum_${portal.id}_${workflow.id}`,
      status: "enabled",
      config: {},
      createdAt: workflow.createdAt,
      updatedAt: workflow.updatedAt,
    }))
  );
  return [...derivedBindings, ...addedBindings].map((binding) => ({
    ...binding,
    ...bindingOverrides.get(binding.id),
  }));
}

function appendAuditLog(entry: Omit<AuditLog, "id">) {
  (auditLogsData as AuditLog[]).unshift({
    id: `audit_${Date.now()}`,
    ...entry,
  });
}

export const mockApi = {
  getDashboard: async (): Promise<DashboardData> =>
    delay(dashboardData as DashboardData),

  getIntegrationEndpoints: async (): Promise<IntegrationEndpoints> =>
    delay({ sdmsBaseUrl: "" }),

  getTasks: async (): Promise<AutomationTask[]> => delay(getTasks()),

  getTaskById: (id: string): Promise<AutomationTask | undefined> => {
    const tasks = getTasks();
    return delay(tasks.find((t) => t.id === id));
  },

  createTask: (task: CreateAutomationTaskInput): Promise<AutomationTask> => {
    const now = new Date().toISOString().replace("T", " ").slice(0, 19);
    const binding = getWorkflowBindings().find(
      (item) => item.id === task.workflowBindingId
    );
    const portal = findPortalById(task.portalAccountId);
    const workflow = getWorkflows().find(
      (item) => item.id === binding?.workflowTemplateId
    );
    const newTask: AutomationTask = {
      id: `task_${Date.now()}`,
      title: task.title,
      taskType: task.taskType,
      entityType: task.entityType,
      erpEntityCode: task.erpEntityCode,
      erpEntityName: task.erpEntityName,
      customerId: task.erpEntityCode,
      customerName: task.erpEntityName,
      portalId: task.portalAccountId,
      srmPortalName: portal?.portalName ?? "",
      workflowBindingId: task.workflowBindingId,
      workflowTemplateId: workflow?.id ?? "",
      workflowTemplateName: workflow?.name ?? "",
      status: "READY",
      priority: task.priority,
      owner: task.assignedTo ?? "当前用户",
      input: task.input,
      currentStep: "等待执行",
      progress: 0,
      createdAt: now,
      updatedAt: now,
    };
    useTaskStore.getState().addTask(newTask);
    return delay(newTask);
  },

  updateTaskStatus: (
    id: string,
    status: AutomationTaskStatus
  ): Promise<AutomationTask | undefined> => {
    useTaskStore.getState().updateTaskStatus(id, status);
    const task = getTasks().find((t) => t.id === id);
    return delay(task);
  },

  updateTask: (
    id: string,
    patch: Partial<AutomationTask>
  ): Promise<AutomationTask | undefined> => {
    useTaskStore.getState().updateTask(id, patch);
    const task = getTasks().find((t) => t.id === id);
    return delay(task);
  },

  getWorkflowTemplates: async (): Promise<WorkflowTemplate[]> =>
    delay(getWorkflows()),

  getWorkflowById: async (id: string): Promise<WorkflowTemplate | undefined> =>
    delay(getWorkflows().find((w) => w.id === id)),

  createWorkflowTemplate: (
    input: CreateWorkflowTemplateInput
  ): Promise<WorkflowTemplate> => {
    const timestamp = now();
    const workflow: WorkflowTemplate = {
      id: newId("workflow"),
      name: input.name,
      code: input.code,
      description: input.description ?? "",
      entityType: input.entityType,
      category: input.category,
      version: input.version,
      status: input.status,
      target: "web",
      inputSchema:
        input.inputSchema as unknown as WorkflowTemplate["inputSchema"],
      steps: input.businessSteps as unknown as WorkflowTemplate["steps"],
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    addedWorkflows.push(workflow);
    return delay(workflow);
  },

  updateWorkflowTemplate: (
    id: string,
    input: UpdateWorkflowTemplateInput
  ): Promise<WorkflowTemplate> => {
    const current = getWorkflows().find((workflow) => workflow.id === id);
    if (!current) {
      throw new Error("工作流模板不存在");
    }
    const patch: Partial<WorkflowTemplate> = {
      ...(input.name === undefined ? {} : { name: input.name }),
      ...(input.description === undefined
        ? {}
        : { description: input.description }),
      ...(input.entityType === undefined
        ? {}
        : { entityType: input.entityType }),
      ...(input.category === undefined ? {} : { category: input.category }),
      ...(input.status === undefined ? {} : { status: input.status }),
      ...(input.version === undefined ? {} : { version: input.version }),
      ...(input.inputSchema === undefined
        ? {}
        : {
            inputSchema:
              input.inputSchema as unknown as WorkflowTemplate["inputSchema"],
          }),
      ...(input.businessSteps === undefined
        ? {}
        : {
            steps: input.businessSteps as unknown as WorkflowTemplate["steps"],
          }),
      updatedAt: now(),
    };
    workflowOverrides.set(id, {
      ...workflowOverrides.get(id),
      ...patch,
    });
    return delay({ ...current, ...patch });
  },

  setWorkflowTemplateStatus: (
    id: string,
    status: "enabled" | "disabled"
  ): Promise<WorkflowTemplate> => {
    const current = getWorkflows().find((workflow) => workflow.id === id);
    if (!current) {
      throw new Error("工作流模板不存在");
    }
    const patch: Partial<WorkflowTemplate> = { status, updatedAt: now() };
    workflowOverrides.set(id, {
      ...workflowOverrides.get(id),
      ...patch,
    });
    return delay({ ...current, ...patch });
  },

  deleteWorkflowTemplate: (id: string): Promise<void> => {
    const workflow = getWorkflows().find((item) => item.id === id);
    if (!workflow) {
      throw new Error("工作流模板不存在");
    }
    if (workflow.status === "enabled") {
      throw new Error("启用中的模板不能删除，请先禁用");
    }
    if (
      getWorkflowBindings().some(
        (binding) => binding.workflowTemplateId === workflow.id
      )
    ) {
      throw new Error("模板已被 Binding 引用，只能禁用");
    }
    if (getTasks().some((task) => task.workflowTemplateId === workflow.id)) {
      throw new Error("模板已被历史任务引用，只能禁用");
    }
    deletedWorkflowIds.add(id);
    workflowOverrides.delete(id);
    return delay(undefined);
  },

  getWorkflowBindings: async (): Promise<WorkflowBinding[]> =>
    delay(getWorkflowBindings()),

  createWorkflowBinding: (
    input: CreateWorkflowBindingInput
  ): Promise<WorkflowBinding> => {
    const timestamp = now();
    const binding: WorkflowBinding = {
      ...input,
      id: newId("binding"),
      rpaFlowVersionId: newId("flow_version"),
      flowChecksumSnapshot: `sha256:mock-${Date.now()}`,
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    addedBindings.push(binding);
    return delay(binding);
  },

  updateWorkflowBinding: (
    id: string,
    input: UpdateWorkflowBindingInput
  ): Promise<WorkflowBinding> => {
    const current = getWorkflowBindings().find((binding) => binding.id === id);
    if (!current) {
      throw new Error("工作流绑定不存在");
    }
    const patch: Partial<WorkflowBinding> = {
      ...input,
      updatedAt: now(),
    };
    bindingOverrides.set(id, {
      ...bindingOverrides.get(id),
      ...patch,
    });
    return delay({ ...current, ...patch });
  },

  setWorkflowBindingStatus: (
    id: string,
    status: WorkflowBindingStatus
  ): Promise<WorkflowBinding> => {
    const current = getWorkflowBindings().find((binding) => binding.id === id);
    if (!current) {
      throw new Error("工作流绑定不存在");
    }
    const patch: Partial<WorkflowBinding> = { status, updatedAt: now() };
    bindingOverrides.set(id, {
      ...bindingOverrides.get(id),
      ...patch,
    });
    return delay({ ...current, ...patch });
  },

  getRuns: async (): Promise<TaskRun[]> => delay(taskRunsData as TaskRun[]),

  getRunById: async (id: string): Promise<TaskRun | undefined> =>
    delay((taskRunsData as TaskRun[]).find((r) => r.id === id)),

  getRunsByTaskId: async (taskId: string): Promise<TaskRun[]> =>
    delay((taskRunsData as TaskRun[]).filter((r) => r.taskId === taskId)),

  getArtifacts: async (): Promise<Artifact[]> =>
    delay(artifactsData as Artifact[]),

  getArtifactsByTaskId: async (taskId: string): Promise<Artifact[]> =>
    delay((artifactsData as Artifact[]).filter((a) => a.taskId === taskId)),

  getArtifactsByRunId: async (runId: string): Promise<Artifact[]> =>
    delay((artifactsData as Artifact[]).filter((a) => a.runId === runId)),

  getWorkers: async (): Promise<Worker[]> => delay(workersData as Worker[]),

  getSrmPortals: async (): Promise<PortalAccount[]> => delay(getPortals()),

  getSrmPortalById: async (id: string): Promise<PortalAccount | undefined> =>
    delay(findPortalById(id)),

  listOwnerCandidates: async () =>
    delay([{ userId: "mock-user", name: "Mock 用户", username: "mock-user" }]),

  createPortalAccount: (
    input: CreatePortalAccountInput
  ): Promise<PortalAccount> => {
    const timestamp = now();
    const sessionPartition =
      input.clientSessionPartition ||
      `persist:portal-${input.erpEntityCode.toLowerCase()}`;
    const created: PortalAccount = {
      ...input,
      id: `portal_${Date.now()}`,
      tenantId: "mock-tenant",
      clientSessionPartition: sessionPartition,
      ownerUserId: input.ownerUserId || "mock-user",
      ownerName: input.ownerName || "Mock 用户",
      createdBy: "mock-user",
      createdByName: input.createdByName || "Mock 用户",
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    mockPortalStore.push(created);
    return delay(created);
  },

  updatePortalAccount: (
    id: string,
    patch: UpdatePortalAccountInput
  ): Promise<PortalAccount> => {
    const index = mockPortalStore.findIndex((p) => p.id === id);
    if (index < 0) {
      throw new Error("门户不存在");
    }
    const existing = mockPortalStore[index];
    if (!existing) {
      throw new Error("门户不存在");
    }
    const updated: PortalAccount = {
      ...existing,
      ...patch,
      updatedAt: now(),
    };
    mockPortalStore[index] = updated;
    return delay(updated);
  },

  deletePortalAccount: (id: string): Promise<void> => {
    const index = mockPortalStore.findIndex((p) => p.id === id);
    if (index < 0) {
      throw new Error("门户不存在");
    }
    mockPortalStore.splice(index, 1);
    return delay(undefined);
  },

  testOpenPortalAccount: (id: string): Promise<PortalAccount | undefined> => {
    const portal = findPortalById(id);
    if (!portal) {
      throw new Error("门户不存在");
    }
    if (portal.status !== "ENABLED") {
      throw new Error("门户已禁用，无法打开");
    }
    const index = mockPortalStore.findIndex((p) => p.id === id);
    if (index >= 0) {
      mockPortalStore[index] = {
        ...portal,
        updatedAt: now(),
      };
    }
    return delay(mockPortalStore[index]);
  },

  getRpaComponents: async (): Promise<RpaComponent[]> =>
    delay(rpaComponentsData as RpaComponent[]),

  getAuditLogs: (taskId?: string): Promise<AuditLog[]> => {
    const logs = auditLogsData as AuditLog[];
    return delay(taskId ? logs.filter((l) => l.taskId === taskId) : logs);
  },

  getIntegrationCallsByTaskId: async (
    _taskId: string
  ): Promise<IntegrationCallLog[]> => delay([]),

  listSchedulerJobs: async (enabled?: boolean) => {
    const jobs = mockSchedulerJobs.filter((job) =>
      enabled === undefined ? true : job.enabled === enabled
    );
    return delay(jobs);
  },

  getSchedulerJob: async (id: string) => {
    const job = mockSchedulerJobs.find((item) => item.id === id);
    if (!job) {
      throw new Error("调度任务不存在");
    }
    return delay(job);
  },

  patchSchedulerJob: async (
    id: string,
    patch: { enabled?: boolean; cron?: string }
  ) => {
    const index = mockSchedulerJobs.findIndex((item) => item.id === id);
    if (index < 0) {
      throw new Error("调度任务不存在");
    }
    mockSchedulerJobs[index] = { ...mockSchedulerJobs[index], ...patch };
    return delay(mockSchedulerJobs[index]);
  },

  listSchedulerJobTasks: async (id: string, page = 1) => {
    const items = mockSchedulerJobTasks.filter((task) => task.jobId === id);
    return delay({
      items,
      total: items.length,
      page,
      pageSize: 20,
    });
  },

  getSettings: async (): Promise<AppSettings> =>
    delay(useSettingsStore.getState().settings),

  updateSettings: (patch: Partial<AppSettings>): Promise<AppSettings> => {
    useSettingsStore.getState().updateSettings(patch);
    return delay(useSettingsStore.getState().settings);
  },

  search: (query: string) => {
    const q = query.toLowerCase();
    const tasks = getTasks().filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.customerName.toLowerCase().includes(q)
    );
    const workflows = getWorkflows().filter(
      (w) =>
        w.name.toLowerCase().includes(q) || w.code.toLowerCase().includes(q)
    );
    const portals = getPortals().filter(
      (p) =>
        p.portalName.toLowerCase().includes(q) ||
        p.erpEntityName.toLowerCase().includes(q) ||
        p.erpEntityCode.toLowerCase().includes(q) ||
        p.loginAccount.toLowerCase().includes(q)
    );
    const runs = (taskRunsData as TaskRun[]).filter(
      (r) =>
        r.taskTitle.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
    );
    return delay({ tasks, workflows, portals, runs });
  },

  getHumanActions: async (): Promise<HumanAction[]> =>
    delay(getHumanActionsFromStore()),

  getHumanAction: async (taskId: string): Promise<HumanAction | undefined> =>
    delay(getHumanActionByTaskId(taskId)),

  getHumanActionById: async (id: string): Promise<HumanAction | undefined> =>
    delay(getHumanActionById(id)),

  markHumanOpened: (input: {
    taskId: string;
    humanActionId: string;
    openedBy?: string;
    clientTabId?: string;
  }): Promise<{ taskId: string; status: AutomationTaskStatus }> => {
    const task = getTasks().find((t) => t.id === input.taskId);
    if (!task) {
      throw new Error("任务不存在");
    }
    if (task.status !== "WAITING_HUMAN" && task.status !== "HUMAN_OPERATING") {
      throw new Error("任务状态不支持打开人工处理");
    }

    const action = getHumanActionById(input.humanActionId);
    if (!action) {
      throw new Error("未找到人工动作");
    }

    const openedAt = now();
    useHumanActionStore.getState().updateHumanAction(input.humanActionId, {
      status: "OPENED",
      openedAt,
    });
    useTaskStore.getState().updateTaskStatus(input.taskId, "HUMAN_OPERATING");

    appendAuditLog({
      taskId: input.taskId,
      action: "human_action.opened",
      operator: input.openedBy ?? "当前用户",
      detail: `打开人工处理页面，Tab: ${input.clientTabId ?? "-"}`,
      createdAt: openedAt,
    });

    return delay({ taskId: input.taskId, status: "HUMAN_OPERATING" });
  },

  confirmHumanAction: (input: {
    taskId: string;
    humanActionId: string;
    confirmedBy?: string;
    note?: string;
  }): Promise<{
    taskId: string;
    status: AutomationTaskStatus;
    confirmedAt: string;
  }> => {
    const task = getTasks().find((t) => t.id === input.taskId);
    if (!task) {
      throw new Error("任务不存在");
    }
    if (task.status !== "WAITING_HUMAN" && task.status !== "HUMAN_OPERATING") {
      throw new Error("任务状态不支持确认完成");
    }

    const confirmedAt = now();
    useTaskStore.getState().updateTask(input.taskId, {
      status: "SUCCESS_MANUAL",
      progress: 100,
      currentStep: "人工确认完成",
    });
    useHumanActionStore.getState().updateHumanAction(input.humanActionId, {
      status: "CONFIRMED",
      confirmedAt,
      confirmedBy: input.confirmedBy ?? "当前用户",
      note: input.note,
    });

    appendAuditLog({
      taskId: input.taskId,
      action: "task.human_confirm",
      operator: input.confirmedBy ?? "当前用户",
      detail: input.note ? `人工确认完成: ${input.note}` : "人工确认完成",
      createdAt: confirmedAt,
    });

    return delay({
      taskId: input.taskId,
      status: "SUCCESS_MANUAL",
      confirmedAt,
    });
  },
};
