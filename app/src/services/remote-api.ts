import { requestAutotaskApi } from "@/actions/autotask-api";
import type { Artifact } from "@/types/artifact";
import type { AuditLog } from "@/types/audit-log";
import type {
  AutomationTask,
  AutomationTaskStatus,
  CreateAutomationTaskInput,
} from "@/types/automation-task";
import type { DashboardData } from "@/types/dashboard";
import type { HumanAction } from "@/types/human-action";
import type {
  CreatePortalAccountInput,
  PortalAccount,
  UpdatePortalAccountInput,
} from "@/types/portal-account";
import type {
  ProcessInstanceDetail,
  ProcessInstanceListItem,
  ProcessLineItem,
  ProcessScanResult,
  ProcessSignPollRunResult,
} from "@/types/process-instance";
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
import {
  createPortalAccount as remoteCreatePortalAccount,
  deletePortalAccount as remoteDeletePortalAccount,
  getPortalAccount as remoteGetPortalAccount,
  listPortalAccounts as remoteListPortalAccounts,
  testOpenPortalAccount as remoteTestOpenPortalAccount,
  updatePortalAccount as remoteUpdatePortalAccount,
} from "./autotask-api/portal-accounts";
import { mapItemResponse, mapListResponse } from "./dto-mappers";
import {
  mapRemoteArtifact,
  mapRemoteBinding,
  mapRemoteHumanAction,
  mapRemoteRun,
  mapRemoteTask,
  mapRemoteWorker,
  mapRemoteWorkflow,
  toRemoteBindingCreate,
  toRemoteBindingUpdate,
  toRemoteTaskCreate,
  toRemoteTaskPatch,
  toRemoteWorkflowCreate,
  toRemoteWorkflowUpdate,
} from "./remote-dto-mappers";

function responseId(value: unknown): string {
  const item = mapItemResponse<{ id?: unknown }>(value);
  return typeof item.id === "string" ? item.id : "";
}

async function getRunChildren(runId: string): Promise<{
  events: unknown[];
  steps: unknown[];
}> {
  const [eventsData, stepsData] = await Promise.all([
    requestAutotaskApi<unknown>({
      method: "GET",
      path: `/runs/${runId}/events`,
    }),
    requestAutotaskApi<unknown>({
      method: "GET",
      path: `/runs/${runId}/step-runs`,
    }),
  ]);
  return {
    events: mapListResponse<unknown>(eventsData),
    steps: mapListResponse<unknown>(stepsData),
  };
}

interface RemoteDashboardSummary {
  completedToday?: number;
  failed?: number;
  onlineWorkers?: number;
  pending?: number;
  ready?: number;
  running?: number;
  stats?: DashboardData["stats"];
  success?: number;
  successRate?: number;
  taskTypeDistribution?: DashboardData["taskTypeDistribution"];
  todayTotal?: number;
  waitingHuman?: number;
}

function mapDashboardSummary(data: unknown): DashboardData {
  const summary = mapItemResponse<RemoteDashboardSummary>(data);

  if (summary.stats) {
    return {
      stats: {
        pending: summary.stats.pending ?? 0,
        running: summary.stats.running ?? 0,
        waitingHuman: summary.stats.waitingHuman ?? 0,
        failed: summary.stats.failed ?? 0,
        completedToday: summary.stats.completedToday ?? 0,
        successRate: summary.stats.successRate ?? 0,
      },
      taskTypeDistribution: summary.taskTypeDistribution ?? [],
    };
  }

  return {
    stats: {
      pending: summary.pending ?? summary.ready ?? 0,
      running: summary.running ?? 0,
      waitingHuman: summary.waitingHuman ?? 0,
      failed: summary.failed ?? 0,
      completedToday: summary.completedToday ?? summary.success ?? 0,
      successRate: summary.successRate ?? 0,
    },
    taskTypeDistribution: summary.taskTypeDistribution ?? [],
  };
}

export const remoteApi = {
  getDashboard: async (): Promise<DashboardData> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/dashboard/summary",
    });
    return mapDashboardSummary(data);
  },

  getTasks: async (): Promise<AutomationTask[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/tasks",
    });
    return mapListResponse<unknown>(data).map(mapRemoteTask);
  },

  getTaskById: async (id: string): Promise<AutomationTask | undefined> => {
    try {
      const data = await requestAutotaskApi<unknown>({
        method: "GET",
        path: `/tasks/${id}`,
      });
      return mapRemoteTask(mapItemResponse<unknown>(data));
    } catch {
      return;
    }
  },

  createTask: async (
    task: CreateAutomationTaskInput
  ): Promise<AutomationTask> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: "/tasks",
      body: toRemoteTaskCreate(task),
    });
    const id = responseId(data);
    const created = id ? await remoteApi.getTaskById(id) : undefined;
    if (!created) {
      throw new Error("任务已创建，但无法读取任务详情");
    }
    return created;
  },

  updateTask: async (
    id: string,
    patch: Partial<AutomationTask>
  ): Promise<AutomationTask | undefined> => {
    const data = await requestAutotaskApi<unknown>({
      method: "PATCH",
      path: `/tasks/${id}`,
      body: toRemoteTaskPatch(patch),
    });
    const updatedId = responseId(data) || id;
    return remoteApi.getTaskById(updatedId);
  },

  startTask: async (id: string): Promise<AutomationTask> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/tasks/${id}/start`,
    });
    const task = await remoteApi.getTaskById(responseId(data) || id);
    if (!task) {
      throw new Error("任务已启动，但无法读取任务详情");
    }
    return task;
  },

  cancelTask: async (id: string): Promise<AutomationTask> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/tasks/${id}/cancel`,
    });
    const task = await remoteApi.getTaskById(responseId(data) || id);
    if (!task) {
      throw new Error("任务已取消，但无法读取任务详情");
    }
    return task;
  },

  retryTask: async (id: string): Promise<AutomationTask> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/tasks/${id}/retry`,
    });
    const task = await remoteApi.getTaskById(responseId(data) || id);
    if (!task) {
      throw new Error("任务已重试，但无法读取任务详情");
    }
    return task;
  },

  updateTaskStatus: async (
    id: string,
    status: AutomationTaskStatus
  ): Promise<AutomationTask | undefined> =>
    remoteApi.updateTask(id, { status }),

  getWorkflowTemplates: async (): Promise<WorkflowTemplate[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/workflow-templates",
    });
    return mapListResponse<unknown>(data).map(mapRemoteWorkflow);
  },

  getWorkflowById: async (
    id: string
  ): Promise<WorkflowTemplate | undefined> => {
    try {
      const data = await requestAutotaskApi<unknown>({
        method: "GET",
        path: `/workflow-templates/${id}`,
      });
      return mapRemoteWorkflow(mapItemResponse<unknown>(data));
    } catch {
      return;
    }
  },

  createWorkflowTemplate: async (
    input: CreateWorkflowTemplateInput
  ): Promise<WorkflowTemplate> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: "/workflow-templates",
      body: toRemoteWorkflowCreate(input),
    });
    return mapRemoteWorkflow(mapItemResponse<unknown>(data));
  },

  updateWorkflowTemplate: async (
    id: string,
    input: UpdateWorkflowTemplateInput
  ): Promise<WorkflowTemplate> => {
    const data = await requestAutotaskApi<unknown>({
      method: "PATCH",
      path: `/workflow-templates/${id}`,
      body: toRemoteWorkflowUpdate(input),
    });
    return mapRemoteWorkflow(mapItemResponse<unknown>(data));
  },

  setWorkflowTemplateStatus: async (
    id: string,
    status: "enabled" | "disabled"
  ): Promise<WorkflowTemplate> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/workflow-templates/${id}/${status === "enabled" ? "enable" : "disable"}`,
    });
    return mapRemoteWorkflow(mapItemResponse<unknown>(data));
  },

  deleteWorkflowTemplate: async (id: string): Promise<void> => {
    await requestAutotaskApi<unknown>({
      method: "DELETE",
      path: `/workflow-templates/${id}`,
    });
  },

  getWorkflowBindings: async (): Promise<WorkflowBinding[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/workflow-bindings",
    });
    return mapListResponse<unknown>(data).map(mapRemoteBinding);
  },

  createWorkflowBinding: async (
    input: CreateWorkflowBindingInput
  ): Promise<WorkflowBinding> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: "/workflow-bindings",
      body: toRemoteBindingCreate(input),
    });
    return mapRemoteBinding(mapItemResponse<unknown>(data));
  },

  updateWorkflowBinding: async (
    id: string,
    input: UpdateWorkflowBindingInput
  ): Promise<WorkflowBinding> => {
    const data = await requestAutotaskApi<unknown>({
      method: "PATCH",
      path: `/workflow-bindings/${id}`,
      body: toRemoteBindingUpdate(input),
    });
    return mapRemoteBinding(mapItemResponse<unknown>(data));
  },

  setWorkflowBindingStatus: async (
    id: string,
    status: WorkflowBindingStatus
  ): Promise<WorkflowBinding> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/workflow-bindings/${id}/${status === "enabled" ? "enable" : "disable"}`,
    });
    return mapRemoteBinding(mapItemResponse<unknown>(data));
  },

  getRuns: async (): Promise<TaskRun[]> => {
    const [data, tasks] = await Promise.all([
      requestAutotaskApi<unknown>({
        method: "GET",
        path: "/runs",
      }),
      remoteApi.getTasks(),
    ]);
    const taskMap = new Map(tasks.map((task) => [task.id, task]));
    return mapListResponse<unknown>(data).map((item) => {
      const base = mapRemoteRun(item);
      return mapRemoteRun(item, { task: taskMap.get(base.taskId) });
    });
  },

  getRunById: async (id: string): Promise<TaskRun | undefined> => {
    try {
      const data = await requestAutotaskApi<unknown>({
        method: "GET",
        path: `/runs/${id}`,
      });
      const rawRun = mapItemResponse<unknown>(data);
      const base = mapRemoteRun(rawRun);
      const [task, children] = await Promise.all([
        remoteApi.getTaskById(base.taskId),
        getRunChildren(id),
      ]);
      return mapRemoteRun(rawRun, {
        task,
        events: children.events,
        steps: children.steps,
      });
    } catch {
      return;
    }
  },

  getRunsByTaskId: async (taskId: string): Promise<TaskRun[]> => {
    const [data, task] = await Promise.all([
      requestAutotaskApi<unknown>({
        method: "GET",
        path: "/runs",
        query: { task_id: taskId },
      }),
      remoteApi.getTaskById(taskId),
    ]);
    return Promise.all(
      mapListResponse<unknown>(data).map(async (item) => {
        const base = mapRemoteRun(item);
        const children = await getRunChildren(base.id);
        return mapRemoteRun(item, {
          task,
          events: children.events,
          steps: children.steps,
        });
      })
    );
  },

  getRunEvents: async (runId: string): Promise<TaskRun | undefined> =>
    remoteApi.getRunById(runId),

  getArtifacts: async (): Promise<Artifact[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/artifacts",
    });
    return mapListResponse<unknown>(data).map(mapRemoteArtifact);
  },

  getArtifactsByTaskId: async (taskId: string): Promise<Artifact[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/artifacts",
      query: { task_id: taskId },
    });
    return mapListResponse<unknown>(data).map(mapRemoteArtifact);
  },

  getArtifactsByRunId: async (runId: string): Promise<Artifact[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/artifacts",
      query: { run_id: runId },
    });
    return mapListResponse<unknown>(data).map(mapRemoteArtifact);
  },

  getArtifactDownloadUrl: async (id: string): Promise<string> => {
    const data = await requestAutotaskApi<{
      url?: string;
      download_url?: string;
    }>({
      method: "GET",
      path: `/artifacts/${id}/download-url`,
    });
    return data.url ?? data.download_url ?? "";
  },

  getWorkers: async (): Promise<Worker[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/rpa-workers",
    });
    return mapListResponse<unknown>(data).map(mapRemoteWorker);
  },

  getSrmPortals: async (): Promise<PortalAccount[]> =>
    remoteListPortalAccounts(),

  getSrmPortalById: async (id: string): Promise<PortalAccount | undefined> =>
    remoteGetPortalAccount(id),

  createPortalAccount: async (
    input: CreatePortalAccountInput
  ): Promise<PortalAccount> => remoteCreatePortalAccount(input),

  updatePortalAccount: async (
    id: string,
    patch: UpdatePortalAccountInput
  ): Promise<PortalAccount> => remoteUpdatePortalAccount(id, patch),

  deletePortalAccount: async (id: string): Promise<void> =>
    remoteDeletePortalAccount(id),

  testOpenPortalAccount: async (
    id: string
  ): Promise<PortalAccount | undefined> => remoteTestOpenPortalAccount(id),

  getRpaComponents: async (): Promise<RpaComponent[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/rpa-components",
    });
    return mapListResponse<RpaComponent>(data);
  },

  listProcessInstances: async (params?: {
    stage?: string;
    status?: string;
    keyword?: string;
  }): Promise<ProcessInstanceListItem[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/process-instances",
      query: params,
    });
    return mapListResponse<ProcessInstanceListItem>(data);
  },

  getProcessInstance: async (
    id: string
  ): Promise<ProcessInstanceDetail | undefined> => {
    try {
      const data = await requestAutotaskApi<unknown>({
        method: "GET",
        path: `/process-instances/${id}`,
      });
      return mapItemResponse<ProcessInstanceDetail>(data);
    } catch {
      return;
    }
  },

  submitProcessLineDate: async (input: {
    instanceId: string;
    lineNumber: string;
    expectedDeliveryDate: string;
  }): Promise<ProcessLineItem> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/process-instances/${input.instanceId}/lines/${input.lineNumber}/date`,
      body: { expectedDeliveryDate: input.expectedDeliveryDate },
    });
    return mapItemResponse<ProcessLineItem>(data);
  },

  signProcessInstance: async (id: string): Promise<ProcessInstanceListItem> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/process-instances/${id}/sign`,
    });
    return mapItemResponse<ProcessInstanceListItem>(data);
  },

  archiveProcessInstance: async (
    id: string
  ): Promise<ProcessInstanceListItem> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/process-instances/${id}/archive`,
    });
    return mapItemResponse<ProcessInstanceListItem>(data);
  },

  retryProcessInstance: async (id: string): Promise<ProcessInstanceListItem> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/process-instances/${id}/retry`,
    });
    return mapItemResponse<ProcessInstanceListItem>(data);
  },

  cancelProcessInstance: async (id: string): Promise<ProcessInstanceListItem> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/process-instances/${id}/cancel`,
    });
    return mapItemResponse<ProcessInstanceListItem>(data);
  },

  triggerProcessScan: async (
    portalAccountId: string
  ): Promise<ProcessScanResult> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: "/process-instances/scan",
      body: { portalAccountId },
    });
    return mapItemResponse<ProcessScanResult>(data);
  },

  runSignPollOnce: async (): Promise<ProcessSignPollRunResult> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: "/process-instances/sign-poll/run-once",
    });
    return mapItemResponse<ProcessSignPollRunResult>(data);
  },

  getAuditLogs: async (taskId?: string): Promise<AuditLog[]> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/audit-logs",
      query: taskId ? { task_id: taskId } : undefined,
    });
    return mapListResponse<AuditLog>(data);
  },

  getSettings: async (): Promise<AppSettings> => {
    const data = await requestAutotaskApi<unknown>({
      method: "GET",
      path: "/settings",
    });
    return mapItemResponse<AppSettings>(data);
  },

  updateSettings: async (patch: Partial<AppSettings>): Promise<AppSettings> => {
    const data = await requestAutotaskApi<unknown>({
      method: "PATCH",
      path: "/settings",
      body: patch,
    });
    return mapItemResponse<AppSettings>(data);
  },

  getHumanAction: async (taskId: string): Promise<HumanAction | undefined> => {
    try {
      const data = await requestAutotaskApi<unknown>({
        method: "GET",
        path: `/tasks/${taskId}/human-action`,
      });
      const item = mapItemResponse<unknown>(data);
      return item === null ? undefined : mapRemoteHumanAction(item);
    } catch {
      return;
    }
  },

  markHumanOpened: async (input: {
    taskId: string;
    humanActionId: string;
    openedBy?: string;
    clientTabId?: string;
  }): Promise<{ taskId: string; status: AutomationTaskStatus }> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/tasks/${input.taskId}/human-opened`,
      body: input,
    });
    return mapItemResponse<{ taskId: string; status: AutomationTaskStatus }>(
      data
    );
  },

  confirmHumanAction: async (input: {
    taskId: string;
    humanActionId: string;
    confirmedBy?: string;
    note?: string;
  }): Promise<{
    taskId: string;
    status: AutomationTaskStatus;
    confirmedAt: string;
  }> => {
    const data = await requestAutotaskApi<unknown>({
      method: "POST",
      path: `/tasks/${input.taskId}/confirm-human`,
      body: input,
    });
    return mapItemResponse<{
      taskId: string;
      status: AutomationTaskStatus;
      confirmedAt: string;
    }>(data);
  },

  search: async (query: string) => {
    const [tasks, workflows, portals, runs] = await Promise.all([
      remoteApi.getTasks(),
      remoteApi.getWorkflowTemplates(),
      remoteApi.getSrmPortals(),
      remoteApi.getRuns(),
    ]);
    const q = query.toLowerCase();
    return {
      tasks: tasks.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.customerName.toLowerCase().includes(q)
      ),
      workflows: workflows.filter(
        (w) =>
          w.name.toLowerCase().includes(q) || w.code.toLowerCase().includes(q)
      ),
      portals: portals.filter(
        (p) =>
          p.portalName.toLowerCase().includes(q) ||
          p.erpEntityName.toLowerCase().includes(q)
      ),
      runs: runs.filter(
        (r) =>
          r.taskTitle.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q)
      ),
    };
  },
};
