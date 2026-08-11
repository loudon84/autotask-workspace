import type { AutomationTaskStatus } from "./automation-task";

export type StepRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "WAITING_HUMAN";

export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

export interface RunLog {
  id: string;
  level: LogLevel;
  message: string;
  timestamp: string;
}

export interface StepRun {
  id: string;
  stepId: string;
  stepName: string;
  stepType: string;
  status: StepRunStatus;
  startedAt?: string;
  endedAt?: string;
  message?: string;
  artifacts?: string[];
}

export interface TaskRun {
  id: string;
  taskId: string;
  taskTitle: string;
  workflowTemplateName: string;
  workerId: string;
  status: AutomationTaskStatus;
  currentStepId?: string;
  startedAt: string;
  endedAt?: string;
  durationSeconds?: number;
  stepRuns: StepRun[];
  logs: RunLog[];
}
