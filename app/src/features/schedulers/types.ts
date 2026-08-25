export interface SchedulerJob {
  id: string;
  bindingId: string;
  portalAccountId: string;
  portalName: string;
  name: string;
  cron: string;
  enabled: boolean;
  nextRunAt: string | null;
}

export interface SchedulerJobTask {
  id: string;
  title: string;
  status: string;
  createdAt: string;
}

export interface SchedulerJobTaskPage {
  items: SchedulerJobTask[];
  total: number;
  page: number;
  pageSize: number;
}
