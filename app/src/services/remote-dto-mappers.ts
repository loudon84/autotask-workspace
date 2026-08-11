import type { Artifact, ArtifactType } from "@/types/artifact";
import type {
  AutomationTask,
  AutomationTaskStatus,
  CreateAutomationTaskInput,
  TaskPriority,
} from "@/types/automation-task";
import type { DashboardData } from "@/types/dashboard";
import type { HumanAction, HumanActionType } from "@/types/human-action";
import type {
  CreatePortalAccountInput,
  SRMPortal,
  UpdatePortalAccountInput,
} from "@/types/srm-portal";
import type {
  LogLevel,
  RunLog,
  StepRun,
  StepRunStatus,
  TaskRun,
} from "@/types/task-run";
import type { Worker, WorkerStatus } from "@/types/worker";
import type {
  CreateWorkflowTemplateInput,
  UpdateWorkflowTemplateInput,
  WorkflowInputField,
  WorkflowStep,
  WorkflowTemplate,
} from "@/types/workflow";
import type {
  CreateWorkflowBindingInput,
  UpdateWorkflowBindingInput,
  WorkflowBinding,
  WorkflowBindingStatus,
} from "@/types/workflow-binding";

type UnknownRecord = Record<string, unknown>;

const taskStatuses = new Set<AutomationTaskStatus>([
  "DRAFT",
  "READY",
  "QUEUED",
  "LEASED",
  "RUNNING",
  "WAITING_HUMAN",
  "HUMAN_OPERATING",
  "HUMAN_CONFIRMED",
  "WAITING_RETRY",
  "SUCCESS",
  "SUCCESS_MANUAL",
  "PARTIAL_SUCCESS",
  "FAILED",
  "CANCELLED",
]);

const taskPriorities = new Set<TaskPriority>([
  "low",
  "normal",
  "high",
  "urgent",
]);

const artifactTypes = new Set<ArtifactType>([
  "screenshot",
  "download",
  "upload",
  "trace",
  "dom_snapshot",
  "log",
]);

const stepStatuses = new Set<StepRunStatus>([
  "PENDING",
  "RUNNING",
  "SUCCESS",
  "FAILED",
  "WAITING_HUMAN",
]);

const logLevels = new Set<LogLevel>(["INFO", "WARN", "ERROR", "DEBUG"]);

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeTaskStatus(value: unknown): AutomationTaskStatus {
  const status = asString(value).toUpperCase() as AutomationTaskStatus;
  return taskStatuses.has(status) ? status : "DRAFT";
}

function normalizePriority(value: unknown): TaskPriority {
  const priority = asString(value, "normal").toLowerCase() as TaskPriority;
  return taskPriorities.has(priority) ? priority : "normal";
}

function normalizePortalStatus(value: unknown): SRMPortal["status"] {
  return asString(value).toUpperCase() === "DISABLED" ? "disabled" : "enabled";
}

function normalizeWorkflowStatus(value: unknown): WorkflowTemplate["status"] {
  const status = asString(value).toLowerCase();
  if (status === "enabled" || status === "disabled") {
    return status;
  }
  return "draft";
}

function normalizeBindingStatus(value: unknown): WorkflowBindingStatus {
  return asString(value).toUpperCase() === "ENABLED" ? "enabled" : "disabled";
}

function normalizeWorkerStatus(value: unknown): WorkerStatus {
  const status = asString(value).toUpperCase();
  if (status === "ONLINE") {
    return "online";
  }
  if (status === "BUSY") {
    return "busy";
  }
  return "offline";
}

function normalizeArtifactType(value: unknown): ArtifactType {
  const type = asString(value, "log").toLowerCase() as ArtifactType;
  return artifactTypes.has(type) ? type : "log";
}

function normalizeHumanActionType(value: unknown): HumanActionType {
  const mappings: Record<string, HumanActionType> = {
    CAPTCHA: "manual_captcha",
    MFA: "manual_mfa",
    CAPTCHA_OR_MFA: "manual_captcha",
    MANUAL_CONFIRM: "manual_confirm",
    MANUAL_PORTAL_OPERATION: "manual_exception_handle",
    APPROVE_SUBMIT: "manual_approve",
  };
  const raw = asString(value);
  const mapped = mappings[raw.toUpperCase()];
  if (mapped) {
    return mapped;
  }
  const normalized = raw.toLowerCase();
  if (
    normalized === "manual_confirm" ||
    normalized === "manual_upload" ||
    normalized === "manual_approve" ||
    normalized === "manual_captcha" ||
    normalized === "manual_mfa" ||
    normalized === "manual_exception_handle"
  ) {
    return normalized;
  }
  return "manual_exception_handle";
}

function normalizeStepStatus(value: unknown): StepRunStatus {
  const status = asString(value).toUpperCase() as StepRunStatus;
  return stepStatuses.has(status) ? status : "PENDING";
}

function normalizeLogLevel(value: unknown): LogLevel {
  const level = asString(value).toUpperCase() as LogLevel;
  return logLevels.has(level) ? level : "INFO";
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function mapWorkflowInputField(
  value: unknown,
  index: number
): WorkflowInputField {
  const item = asRecord(value);
  const name = asString(item.name, `input_${index + 1}`);
  return {
    name,
    label: asString(item.label, name),
    type: asString(item.type, "string"),
    required: item.required === true,
  };
}

function mapWorkflowStep(value: unknown, index: number): WorkflowStep {
  const item = asRecord(value);
  const onError = asOptionalString(item.onError);
  const validOnError =
    onError === "fail" ||
    onError === "retry" ||
    onError === "wait_human" ||
    onError === "ignore"
      ? onError
      : undefined;
  return {
    id: asString(item.id, `step_${index + 1}`),
    name: asString(item.name, `步骤 ${index + 1}`),
    type: asString(item.type, "unknown"),
    description: asOptionalString(item.description),
    input: Object.keys(asRecord(item.input)).length
      ? asRecord(item.input)
      : undefined,
    timeout:
      typeof item.timeout === "number" ? asNumber(item.timeout) : undefined,
    retry: typeof item.retry === "number" ? asNumber(item.retry) : undefined,
    onError: validOnError,
  };
}

export function mapRemoteDashboard(value: unknown): DashboardData {
  const data = asRecord(value);
  const stats = asRecord(data.stats);
  return {
    stats: {
      pending: asNumber(stats.pending),
      running: asNumber(stats.running),
      waitingHuman: asNumber(stats.waitingHuman),
      failed: asNumber(stats.failed),
      completedToday: asNumber(stats.completedToday),
      successRate: asNumber(stats.successRate),
    },
    taskTypeDistribution: asArray(data.taskTypeDistribution).map((entry) => {
      const item = asRecord(entry);
      const taskType = asString(item.taskType);
      return {
        taskType,
        label: asString(item.label, taskType),
        count: asNumber(item.count),
      };
    }),
  };
}

export function mapRemoteTask(value: unknown): AutomationTask {
  const item = asRecord(value);
  return {
    id: asString(item.id),
    title: asString(item.title),
    taskType: asString(item.taskType),
    entityType: asOptionalString(item.entityType),
    erpEntityCode: asOptionalString(item.erpEntityCode),
    erpEntityName: asOptionalString(item.erpEntityName),
    customerId: asOptionalString(item.erpEntityCode),
    customerName: asString(item.customerName, asString(item.erpEntityName)),
    portalId: asOptionalString(item.portalId ?? item.portalAccountId),
    srmPortalName: asString(item.srmPortalName),
    workflowBindingId: asOptionalString(item.workflowBindingId),
    workflowTemplateId: asString(item.workflowTemplateId),
    workflowTemplateName: asString(item.workflowTemplateName),
    status: normalizeTaskStatus(item.status),
    priority: normalizePriority(item.priority),
    owner: asString(
      item.owner,
      asString(item.assignedTo, asString(item.createdBy))
    ),
    input: asRecord(item.input),
    currentStep: asOptionalString(item.currentStep),
    progress: asNumber(item.progress),
    createdAt: asString(item.createdAt),
    updatedAt: asString(item.updatedAt),
  };
}

export function mapRemotePortal(value: unknown): SRMPortal {
  const item = asRecord(value);
  const id = asString(item.id);
  const portalUrl = asString(item.portalUrl, asString(item.url));
  const clientOpenMode =
    item.clientOpenMode === "system_browser" ? "system_browser" : "webcontents";
  return {
    id,
    entityType: asOptionalString(item.entityType),
    erpEntityCode: asOptionalString(item.erpEntityCode),
    loginAccount: asOptionalString(item.loginAccount),
    customerName: asString(item.customerName, asString(item.erpEntityName)),
    name: asString(item.name, asString(item.portalName)),
    url: portalUrl,
    loginType: "username_password",
    status: normalizePortalStatus(item.status),
    clientOpenMode,
    clientSessionPartition:
      asOptionalString(item.clientSessionPartition) ?? `persist:srm:${id}`,
    loginState: "unknown",
    locatorProfile: {},
    loginPageUrl: portalUrl,
    createdAt: asString(item.createdAt),
    updatedAt: asString(item.updatedAt),
  };
}

export function mapRemoteWorkflow(value: unknown): WorkflowTemplate {
  const item = asRecord(value);
  const rawSteps =
    item.businessSteps === undefined ? item.steps : item.businessSteps;
  const rawTarget = asString(item.target);
  const target =
    rawTarget === "desktop" || rawTarget === "file" || rawTarget === "hybrid"
      ? rawTarget
      : "web";
  return {
    id: asString(item.id),
    name: asString(item.name),
    code: asString(item.code),
    description: asString(item.description),
    entityType: asOptionalString(item.entityType),
    category: asString(item.category),
    version: asString(item.version),
    status: normalizeWorkflowStatus(item.status),
    target,
    inputSchema: asArray(item.inputSchema).map(mapWorkflowInputField),
    steps: asArray(rawSteps).map(mapWorkflowStep),
    createdAt: asString(item.createdAt),
    updatedAt: asString(item.updatedAt),
  };
}

export function mapRemoteBinding(value: unknown): WorkflowBinding {
  const item = asRecord(value);
  return {
    id: asString(item.id),
    portalAccountId: asString(item.portalAccountId),
    workflowTemplateId: asString(item.workflowTemplateId),
    workflowTemplateVersion: asString(item.workflowTemplateVersion),
    rpaEngineType: asString(item.rpaEngineType),
    rpaFlowId: asString(item.rpaFlowId),
    rpaFlowVersion: asString(item.rpaFlowVersion),
    rpaFlowVersionId: asOptionalString(item.rpaFlowVersionId),
    flowChecksumSnapshot: asOptionalString(item.flowChecksumSnapshot),
    status: normalizeBindingStatus(item.status),
    config: asRecord(item.config),
    createdAt: asString(item.createdAt),
    updatedAt: asString(item.updatedAt),
  };
}

export function mapRemoteWorker(value: unknown): Worker {
  const item = asRecord(value);
  return {
    id: asString(item.id),
    name: asString(item.name),
    status: normalizeWorkerStatus(item.status),
    currentTaskCount: asNumber(item.currentTaskCount),
    browserCount: asNumber(item.browserCount),
    cpuUsage: `${asNumber(item.cpuUsage)}%`,
    memoryUsage: `${asNumber(item.memoryUsage)}%`,
    lastHeartbeat: asString(item.lastHeartbeatAt, asString(item.lastHeartbeat)),
  };
}

export function mapRemoteArtifact(value: unknown): Artifact {
  const item = asRecord(value);
  const size = asNumber(item.size);
  const storageKey = asString(item.storageKey);
  return {
    id: asString(item.id),
    taskId: asString(item.taskId),
    runId: asString(item.runId),
    name: asString(item.name),
    type: normalizeArtifactType(item.type),
    filePath: storageKey,
    storageKey,
    size,
    sizeText: formatBytes(size),
    mimeType: asOptionalString(item.mimeType),
    createdAt: asString(item.createdAt),
  };
}

function mapRemoteEvent(value: unknown): RunLog {
  const item = asRecord(value);
  return {
    id: asString(item.id),
    level: normalizeLogLevel(item.level),
    message: asString(item.message),
    timestamp: asString(item.createdAt),
  };
}

function mapRemoteStepRun(value: unknown): StepRun {
  const item = asRecord(value);
  return {
    id: asString(item.id),
    stepId: asString(item.stepId),
    stepName: asString(item.stepName, asString(item.stepId)),
    stepType: "FLOW_STEP",
    status: normalizeStepStatus(item.status),
    message: asOptionalString(asRecord(item.output).message),
  };
}

export interface RemoteRunContext {
  events?: unknown[];
  steps?: unknown[];
  task?: AutomationTask;
}

export function mapRemoteRun(
  value: unknown,
  context: RemoteRunContext = {}
): TaskRun {
  const item = asRecord(value);
  const startedAt = asString(item.startedAt);
  const endedAt = asOptionalString(item.endedAt);
  const startedTimestamp = Date.parse(startedAt);
  const endedTimestamp = endedAt ? Date.parse(endedAt) : Number.NaN;
  const durationSeconds =
    Number.isFinite(startedTimestamp) && Number.isFinite(endedTimestamp)
      ? Math.max(0, Math.round((endedTimestamp - startedTimestamp) / 1000))
      : undefined;
  return {
    id: asString(item.id),
    taskId: asString(item.taskId),
    taskTitle: context.task?.title ?? asString(item.taskTitle),
    workflowTemplateName:
      context.task?.workflowTemplateName ?? asString(item.workflowTemplateName),
    workerId: asString(item.rpaWorkerId, asString(item.workerId, "-")),
    status: normalizeTaskStatus(item.status),
    currentStepId: asOptionalString(item.currentStepId),
    startedAt,
    endedAt,
    durationSeconds,
    stepRuns: (context.steps ?? []).map(mapRemoteStepRun),
    logs: (context.events ?? []).map(mapRemoteEvent),
  };
}

export function mapRemoteHumanAction(value: unknown): HumanAction {
  const item = asRecord(value);
  const payload = asRecord(item.payload);
  return {
    id: asString(item.id),
    taskId: asString(item.taskId),
    runId: asOptionalString(item.runId),
    portalId: asOptionalString(payload.portalId ?? payload.portalAccountId),
    type: normalizeHumanActionType(item.type),
    targetUrl: asString(item.targetUrl),
    instruction: asString(item.instruction, asString(item.title)),
    status: asString(item.status, "PENDING") as HumanAction["status"],
    createdAt: asString(item.createdAt),
    openedAt: asOptionalString(item.openedAt),
    confirmedAt: asOptionalString(item.confirmedAt),
    confirmedBy: asOptionalString(item.confirmedBy),
    note: asOptionalString(payload.note),
  };
}

export function toRemoteTaskCreate(
  input: CreateAutomationTaskInput
): UnknownRecord {
  return {
    title: input.title,
    task_type: input.taskType,
    portal_account_id: input.portalAccountId,
    workflow_binding_id: input.workflowBindingId,
    entity_type: input.entityType,
    erp_entity_code: input.erpEntityCode,
    erp_entity_name: input.erpEntityName,
    priority: input.priority.toUpperCase(),
    input: input.input,
    ...(input.assignedTo ? { assigned_to: input.assignedTo } : {}),
  };
}

export function toRemotePortalCreate(
  input: CreatePortalAccountInput
): UnknownRecord {
  return {
    entityType: input.entityType,
    erpEntityCode: input.erpEntityCode,
    erpEntityName: input.erpEntityName,
    portalName: input.portalName,
    portalUrl: input.portalUrl,
    loginAccount: input.loginAccount,
    ...(input.credentialRef ? { credentialRef: input.credentialRef } : {}),
    clientOpenMode: input.clientOpenMode,
    clientSessionPartition: input.clientSessionPartition,
    status: input.status.toUpperCase(),
  };
}

export function toRemotePortalUpdate(
  input: UpdatePortalAccountInput
): UnknownRecord {
  return {
    ...(input.entityType === undefined ? {} : { entityType: input.entityType }),
    ...(input.erpEntityCode === undefined
      ? {}
      : { erpEntityCode: input.erpEntityCode }),
    ...(input.erpEntityName === undefined
      ? {}
      : { erpEntityName: input.erpEntityName }),
    ...(input.portalName === undefined ? {} : { portalName: input.portalName }),
    ...(input.portalUrl === undefined ? {} : { portalUrl: input.portalUrl }),
    ...(input.loginAccount === undefined
      ? {}
      : { loginAccount: input.loginAccount }),
    ...(input.credentialRef === undefined || input.credentialRef === ""
      ? {}
      : { credentialRef: input.credentialRef }),
    ...(input.clientOpenMode === undefined
      ? {}
      : { clientOpenMode: input.clientOpenMode }),
    ...(input.clientSessionPartition === undefined
      ? {}
      : { clientSessionPartition: input.clientSessionPartition }),
    ...(input.status === undefined
      ? {}
      : { status: input.status.toUpperCase() }),
  };
}

export function toRemoteWorkflowCreate(
  input: CreateWorkflowTemplateInput
): UnknownRecord {
  return {
    name: input.name,
    code: input.code,
    description: input.description,
    entity_type: input.entityType,
    category: input.category,
    status: input.status.toUpperCase(),
    version: input.version,
    input_schema: input.inputSchema,
    business_steps: input.businessSteps,
  };
}

export function toRemoteWorkflowUpdate(
  input: UpdateWorkflowTemplateInput
): UnknownRecord {
  return {
    ...(input.name === undefined ? {} : { name: input.name }),
    ...(input.description === undefined
      ? {}
      : { description: input.description }),
    ...(input.entityType === undefined
      ? {}
      : { entity_type: input.entityType }),
    ...(input.category === undefined ? {} : { category: input.category }),
    ...(input.status === undefined
      ? {}
      : { status: input.status.toUpperCase() }),
    ...(input.version === undefined ? {} : { version: input.version }),
    ...(input.inputSchema === undefined
      ? {}
      : { input_schema: input.inputSchema }),
    ...(input.businessSteps === undefined
      ? {}
      : { business_steps: input.businessSteps }),
  };
}

export function toRemoteBindingCreate(
  input: CreateWorkflowBindingInput
): UnknownRecord {
  return {
    portal_account_id: input.portalAccountId,
    workflow_template_id: input.workflowTemplateId,
    workflow_template_version: input.workflowTemplateVersion,
    rpa_engine_type: input.rpaEngineType,
    rpa_flow_id: input.rpaFlowId,
    rpa_flow_version: input.rpaFlowVersion,
    status: input.status.toUpperCase(),
    config: input.config,
  };
}

export function toRemoteBindingUpdate(
  input: UpdateWorkflowBindingInput
): UnknownRecord {
  return {
    ...(input.workflowTemplateVersion === undefined
      ? {}
      : { workflow_template_version: input.workflowTemplateVersion }),
    ...(input.rpaEngineType === undefined
      ? {}
      : { rpa_engine_type: input.rpaEngineType }),
    ...(input.rpaFlowId === undefined ? {} : { rpa_flow_id: input.rpaFlowId }),
    ...(input.rpaFlowVersion === undefined
      ? {}
      : { rpa_flow_version: input.rpaFlowVersion }),
    ...(input.status === undefined
      ? {}
      : { status: input.status.toUpperCase() }),
    ...(input.config === undefined ? {} : { config: input.config }),
  };
}

export function toRemoteTaskPatch(
  patch: Partial<AutomationTask>
): UnknownRecord {
  return {
    ...(patch.title === undefined ? {} : { title: patch.title }),
    ...(patch.priority === undefined
      ? {}
      : { priority: patch.priority.toUpperCase() }),
    ...(patch.input === undefined ? {} : { input: patch.input }),
    ...(patch.currentStep === undefined
      ? {}
      : { current_step: patch.currentStep }),
    ...(patch.progress === undefined ? {} : { progress: patch.progress }),
  };
}
