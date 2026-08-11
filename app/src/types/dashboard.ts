export interface DashboardStats {
  pending: number;
  running: number;
  waitingHuman: number;
  failed: number;
  completedToday: number;
  successRate: number;
}

export interface TaskTypeDistribution {
  taskType: string;
  label: string;
  count: number;
}

export interface DashboardData {
  stats: DashboardStats;
  taskTypeDistribution: TaskTypeDistribution[];
}
