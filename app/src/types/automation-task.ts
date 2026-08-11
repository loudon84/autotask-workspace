import type { HumanAction } from "@/types/human-action";

export type AutomationTaskStatus =
  | "DRAFT"
  | "READY"
  | "QUEUED"
  | "LEASED"
  | "RUNNING"
  | "WAITING_HUMAN"
  | "HUMAN_OPERATING"
  | "HUMAN_CONFIRMED"
  | "WAITING_RETRY"
  | "SUCCESS"
  | "SUCCESS_MANUAL"
  | "PARTIAL_SUCCESS"
  | "FAILED"
  | "CANCELLED";

export type TaskPriority = "low" | "normal" | "high" | "urgent";

export interface CreateAutomationTaskInput {
  assignedTo?: string;
  entityType: string;
  erpEntityCode: string;
  erpEntityName: string;
  input: Record<string, unknown>;
  portalAccountId: string;
  priority: TaskPriority;
  taskType: string;
  title: string;
  workflowBindingId: string;
}

export interface AutomationTask {
  createdAt: string;
  currentStep?: string;
  customerId?: string;
  customerName: string;

  entityType?: string;
  erpEntityCode?: string;
  erpEntityName?: string;
  humanAction?: HumanAction;

  humanActionId?: string;
  id: string;

  input: Record<string, unknown>;
  owner: string;

  portalId?: string;
  priority: TaskPriority;
  progress: number;
  srmPortalName: string;

  status: AutomationTaskStatus;
  taskType: string;
  title: string;
  updatedAt: string;

  workflowBindingId?: string;
  workflowTemplateId: string;
  workflowTemplateName: string;
}
