export interface IntegrationCallLog {
  id: string;
  taskId: string;
  runId?: string | null;
  system: string;
  method: string;
  url: string;
  requestBody?: string | null;
  responseBody?: string | null;
  statusCode?: number | null;
  errorCode?: string | null;
  durationMs?: number | null;
  requestTruncated: boolean;
  responseTruncated: boolean;
  createdAt: string;
}
