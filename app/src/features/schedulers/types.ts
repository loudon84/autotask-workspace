export interface Timer {
  id: string;
  name: string;
  cron: string;
  enabled: boolean;
  nextRunAt: string | null;
}

/** @deprecated 使用 Timer；调度中心已改为独立定时器 */
export type SchedulerJob = Timer;

export interface TimerRun {
  id: string;
  status: "RUNNING" | "SUCCESS" | "FAILED" | "NO_LISTENER";
  triggeredAt: string;
  finishedAt: string | null;
  error: string | null;
}

export interface TimerRunPage {
  items: TimerRun[];
  total: number;
  page: number;
  pageSize: number;
}

export interface TimerRunResult {
  status: string;
  message: string;
  error?: string | null;
}
