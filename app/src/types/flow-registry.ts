export type FlowScope = "GLOBAL" | "TENANT";

export type FlowStatus = "ACTIVE" | "DISABLED" | "ARCHIVED";

export type FlowVersionStatus =
  | "DRAFT"
  | "VALIDATING"
  | "PUBLISHED"
  | "DEPRECATED"
  | "DISABLED";

export type FlowValidationStatus = "PENDING" | "RUNNING" | "PASSED" | "FAILED";

export interface FlowSummary {
  createdAt: string;
  createdBy: string;
  description: string | null;
  id: string;
  labels: string[];
  name: string;
  rpaFlowId: string;
  scope: FlowScope;
  status: FlowStatus;
  tenantId: string | null;
  updatedAt: string;
}

export interface FlowVersion {
  capabilities: string[];
  createdAt: string;
  createdBy: string;
  engineType: string;
  entrypoint: string;
  inputSchema: unknown[];
  manifest: Record<string, unknown>;
  minimumEngineVersion: string | null;
  packageChecksum: string | null;
  packageSizeBytes: number | null;
  packageUri: string | null;
  publishedAt: string | null;
  rpaFlowId: string;
  rpaFlowVersionId: string;
  status: FlowVersionStatus;
  supportedPortalTypes: string[];
  supportedWorkflowCodes: string[];
  updatedAt: string;
  version: string;
}

export interface FlowValidation {
  checks: unknown[];
  createdAt: string;
  endedAt: string | null;
  errors: unknown[];
  flowVersionId: string;
  requestedBy: string;
  resultSummary: string | null;
  startedAt: string | null;
  status: FlowValidationStatus;
  triggerType: string;
  validationRunId: string;
  warnings: unknown[];
}

export interface FlowListResponse {
  items: FlowSummary[];
  limit: number;
  offset: number;
  total: number;
}

export interface FlowPackageUploadResponse {
  flow: FlowSummary;
  validation: FlowValidation;
  version: FlowVersion;
}

export type FlowPackageDialogResult =
  | { cancelled: true }
  | {
      cancelled: false;
      fileName: string;
      fileSize: number;
      upload: FlowPackageUploadResponse;
    };
