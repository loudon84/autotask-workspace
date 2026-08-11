export interface WorkflowInputField {
  name: string;
  label: string;
  type: string;
  required: boolean;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: string;
  description?: string;
  input?: Record<string, unknown>;
  timeout?: number;
  retry?: number;
  onError?: "fail" | "retry" | "wait_human" | "ignore";
}

export interface CreateWorkflowTemplateInput {
  businessSteps: Record<string, unknown>[];
  category: string;
  description?: string;
  entityType: string;
  inputSchema: Record<string, unknown>[];
  name: string;
  status: WorkflowTemplate["status"];
  version: string;
  code: string;
}

export type UpdateWorkflowTemplateInput = Omit<
  Partial<CreateWorkflowTemplateInput>,
  "code"
>;

export interface WorkflowTemplate {
  id: string;
  name: string;
  code: string;
  description: string;
  entityType?: string;
  category: string;
  version: string;
  status: "enabled" | "disabled" | "draft";
  target: "web" | "desktop" | "file" | "hybrid";
  inputSchema: WorkflowInputField[];
  steps: WorkflowStep[];
  createdAt: string;
  updatedAt: string;
}
