export type WorkflowBindingStatus = "enabled" | "disabled";

export interface CreateWorkflowBindingInput {
  config: Record<string, unknown>;
  portalAccountId: string;
  rpaEngineType: string;
  rpaFlowId: string;
  rpaFlowVersion: string;
  status: WorkflowBindingStatus;
  workflowTemplateId: string;
  workflowTemplateVersion: string;
}

export type UpdateWorkflowBindingInput = Partial<
  Omit<CreateWorkflowBindingInput, "portalAccountId" | "workflowTemplateId">
>;

export interface WorkflowBinding {
  config: Record<string, unknown>;
  createdAt: string;
  flowChecksumSnapshot?: string;
  id: string;
  portalAccountId: string;
  rpaEngineType: string;
  rpaFlowId: string;
  rpaFlowVersion: string;
  rpaFlowVersionId?: string;
  status: WorkflowBindingStatus;
  updatedAt: string;
  workflowTemplateId: string;
  workflowTemplateVersion: string;
}
