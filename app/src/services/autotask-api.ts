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
import { getApiMode } from "./endpoint-config";
import { mockApi } from "./mock-api";
import { remoteApi } from "./remote-api";

function pickApi() {
  return getApiMode() === "remote" ? remoteApi : mockApi;
}

export const autotaskApi = {
  dashboard: {
    getSummary: (): Promise<DashboardData> => pickApi().getDashboard(),
  },

  tasks: {
    list: (): Promise<AutomationTask[]> => pickApi().getTasks(),
    get: (id: string): Promise<AutomationTask | undefined> =>
      pickApi().getTaskById(id),
    create: (task: CreateAutomationTaskInput): Promise<AutomationTask> =>
      pickApi().createTask(task),
    update: (
      id: string,
      patch: Partial<AutomationTask>
    ): Promise<AutomationTask | undefined> => pickApi().updateTask(id, patch),
    start: async (id: string): Promise<AutomationTask> => {
      const api = pickApi();
      if ("startTask" in api && typeof api.startTask === "function") {
        return api.startTask(id);
      }
      const result = await api.updateTaskStatus(id, "QUEUED");
      if (!result) {
        throw new Error("任务不存在");
      }
      return result;
    },
    cancel: async (id: string): Promise<AutomationTask> => {
      const api = pickApi();
      if ("cancelTask" in api && typeof api.cancelTask === "function") {
        return api.cancelTask(id);
      }
      const result = await api.updateTaskStatus(id, "CANCELLED");
      if (!result) {
        throw new Error("任务不存在");
      }
      return result;
    },
    retry: async (id: string): Promise<AutomationTask> => {
      const api = pickApi();
      if ("retryTask" in api && typeof api.retryTask === "function") {
        return api.retryTask(id);
      }
      const result = await api.updateTaskStatus(id, "QUEUED");
      if (!result) {
        throw new Error("任务不存在");
      }
      return result;
    },
    updateStatus: (
      id: string,
      status: AutomationTaskStatus
    ): Promise<AutomationTask | undefined> =>
      pickApi().updateTaskStatus(id, status),
    getHumanAction: (taskId: string): Promise<HumanAction | undefined> =>
      pickApi().getHumanAction(taskId),
    markHumanOpened: (input: {
      taskId: string;
      humanActionId: string;
      openedBy?: string;
      clientTabId?: string;
    }) => pickApi().markHumanOpened(input),
    confirmHumanAction: (input: {
      taskId: string;
      humanActionId: string;
      confirmedBy?: string;
      note?: string;
    }) => pickApi().confirmHumanAction(input),
  },

  portalAccounts: {
    list: (): Promise<PortalAccount[]> => pickApi().getSrmPortals(),
    get: (id: string): Promise<PortalAccount | undefined> =>
      pickApi().getSrmPortalById(id),
    create: (input: CreatePortalAccountInput): Promise<PortalAccount> => {
      const api = pickApi();
      if (
        "createPortalAccount" in api &&
        typeof api.createPortalAccount === "function"
      ) {
        return api.createPortalAccount(input);
      }
      throw new Error("当前模式不支持创建门户");
    },
    update: (
      id: string,
      patch: UpdatePortalAccountInput
    ): Promise<PortalAccount> => {
      const api = pickApi();
      if (
        "updatePortalAccount" in api &&
        typeof api.updatePortalAccount === "function"
      ) {
        return api.updatePortalAccount(id, patch);
      }
      throw new Error("当前模式不支持更新门户");
    },
    delete: (id: string): Promise<void> => {
      const api = pickApi();
      if (
        "deletePortalAccount" in api &&
        typeof api.deletePortalAccount === "function"
      ) {
        return api.deletePortalAccount(id);
      }
      throw new Error("当前模式不支持删除门户");
    },
    testOpen: (id: string): Promise<PortalAccount | undefined> => {
      const api = pickApi();
      if (
        "testOpenPortalAccount" in api &&
        typeof api.testOpenPortalAccount === "function"
      ) {
        return api.testOpenPortalAccount(id);
      }
      throw new Error("当前模式不支持打开门户");
    },
  },

  workflowTemplates: {
    list: (): Promise<WorkflowTemplate[]> => pickApi().getWorkflowTemplates(),
    get: (id: string): Promise<WorkflowTemplate | undefined> =>
      pickApi().getWorkflowById(id),
    create: (input: CreateWorkflowTemplateInput): Promise<WorkflowTemplate> =>
      pickApi().createWorkflowTemplate(input),
    update: (
      id: string,
      input: UpdateWorkflowTemplateInput
    ): Promise<WorkflowTemplate> => pickApi().updateWorkflowTemplate(id, input),
    setStatus: (
      id: string,
      status: "enabled" | "disabled"
    ): Promise<WorkflowTemplate> =>
      pickApi().setWorkflowTemplateStatus(id, status),
    delete: (id: string): Promise<void> => pickApi().deleteWorkflowTemplate(id),
  },

  workflowBindings: {
    list: (): Promise<WorkflowBinding[]> => pickApi().getWorkflowBindings(),
    create: (input: CreateWorkflowBindingInput): Promise<WorkflowBinding> =>
      pickApi().createWorkflowBinding(input),
    update: (
      id: string,
      input: UpdateWorkflowBindingInput
    ): Promise<WorkflowBinding> => pickApi().updateWorkflowBinding(id, input),
    setStatus: (
      id: string,
      status: WorkflowBindingStatus
    ): Promise<WorkflowBinding> =>
      pickApi().setWorkflowBindingStatus(id, status),
  },

  runs: {
    list: (): Promise<TaskRun[]> => pickApi().getRuns(),
    get: (id: string): Promise<TaskRun | undefined> => pickApi().getRunById(id),
    listByTask: (taskId: string): Promise<TaskRun[]> =>
      pickApi().getRunsByTaskId(taskId),
    listEvents: (runId: string): Promise<TaskRun | undefined> => {
      const api = pickApi();
      if ("getRunEvents" in api && typeof api.getRunEvents === "function") {
        return api.getRunEvents(runId);
      }
      return api.getRunById(runId);
    },
  },

  artifacts: {
    list: (): Promise<Artifact[]> => pickApi().getArtifacts(),
    listByTask: (taskId: string): Promise<Artifact[]> =>
      pickApi().getArtifactsByTaskId(taskId),
    listByRun: (runId: string): Promise<Artifact[]> =>
      pickApi().getArtifactsByRunId(runId),
    getDownloadUrl: async (id: string): Promise<string> => {
      const api = pickApi();
      if (
        "getArtifactDownloadUrl" in api &&
        typeof api.getArtifactDownloadUrl === "function"
      ) {
        return api.getArtifactDownloadUrl(id);
      }
      const artifact = (await pickApi().getArtifacts()).find(
        (a) => a.id === id
      );
      return artifact?.filePath ?? "";
    },
  },

  workers: {
    list: (): Promise<Worker[]> => pickApi().getWorkers(),
  },

  settings: {
    get: (): Promise<AppSettings> => pickApi().getSettings(),
    update: (patch: Partial<AppSettings>): Promise<AppSettings> =>
      pickApi().updateSettings(patch),
  },

  rpaComponents: {
    list: (): Promise<RpaComponent[]> => pickApi().getRpaComponents(),
  },

  processInstances: {
    list: (params?: {
      stage?: string;
      status?: string;
      keyword?: string;
    }): Promise<ProcessInstanceListItem[]> => {
      const api = pickApi();
      if (
        "listProcessInstances" in api &&
        typeof api.listProcessInstances === "function"
      ) {
        return api.listProcessInstances(params);
      }
      return Promise.resolve([]);
    },
    get: (id: string): Promise<ProcessInstanceDetail | undefined> => {
      const api = pickApi();
      if (
        "getProcessInstance" in api &&
        typeof api.getProcessInstance === "function"
      ) {
        return api.getProcessInstance(id);
      }
      return Promise.resolve(undefined);
    },
    submitLineDate: (input: {
      instanceId: string;
      lineNumber: string;
      expectedDeliveryDate: string;
    }): Promise<ProcessLineItem> => {
      const api = pickApi();
      if (
        "submitProcessLineDate" in api &&
        typeof api.submitProcessLineDate === "function"
      ) {
        return api.submitProcessLineDate(input);
      }
      throw new Error("当前模式不支持提交交货日期");
    },
    sign: (id: string): Promise<ProcessInstanceListItem> => {
      const api = pickApi();
      if (
        "signProcessInstance" in api &&
        typeof api.signProcessInstance === "function"
      ) {
        return api.signProcessInstance(id);
      }
      throw new Error("当前模式不支持发起签章");
    },
    archive: (id: string): Promise<ProcessInstanceListItem> => {
      const api = pickApi();
      if (
        "archiveProcessInstance" in api &&
        typeof api.archiveProcessInstance === "function"
      ) {
        return api.archiveProcessInstance(id);
      }
      throw new Error("当前模式不支持归档");
    },
    retry: (id: string): Promise<ProcessInstanceListItem> => {
      const api = pickApi();
      if (
        "retryProcessInstance" in api &&
        typeof api.retryProcessInstance === "function"
      ) {
        return api.retryProcessInstance(id);
      }
      throw new Error("当前模式不支持重试");
    },
    cancel: (id: string): Promise<ProcessInstanceListItem> => {
      const api = pickApi();
      if (
        "cancelProcessInstance" in api &&
        typeof api.cancelProcessInstance === "function"
      ) {
        return api.cancelProcessInstance(id);
      }
      throw new Error("当前模式不支持取消");
    },
    triggerScan: (portalAccountId: string): Promise<ProcessScanResult> => {
      const api = pickApi();
      if (
        "triggerProcessScan" in api &&
        typeof api.triggerProcessScan === "function"
      ) {
        return api.triggerProcessScan(portalAccountId);
      }
      throw new Error("当前模式不支持手动扫单");
    },
    runSignPollOnce: (): Promise<ProcessSignPollRunResult> => {
      const api = pickApi();
      if (
        "runSignPollOnce" in api &&
        typeof api.runSignPollOnce === "function"
      ) {
        return api.runSignPollOnce();
      }
      throw new Error("当前模式不支持立即回签轮询");
    },
  },

  auditLogs: {
    list: (taskId?: string): Promise<AuditLog[]> =>
      pickApi().getAuditLogs(taskId),
  },

  search: (query: string) => pickApi().search(query),
};
