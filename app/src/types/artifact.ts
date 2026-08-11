export type ArtifactType =
  | "screenshot"
  | "download"
  | "upload"
  | "trace"
  | "dom_snapshot"
  | "log";

export interface Artifact {
  id: string;
  taskId: string;
  runId: string;
  customerName?: string;
  taskTitle?: string;
  name: string;
  type: ArtifactType;
  filePath: string;
  storageKey?: string;
  size?: number;
  sizeText: string;
  mimeType?: string;
  createdAt: string;
}
