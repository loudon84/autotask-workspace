export type WorkerStatus = "online" | "busy" | "offline";

export interface Worker {
  id: string;
  name: string;
  status: WorkerStatus;
  currentTaskCount: number;
  browserCount: number;
  cpuUsage: string;
  memoryUsage: string;
  lastHeartbeat: string;
}
