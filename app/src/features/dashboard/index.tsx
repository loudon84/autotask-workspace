import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { StatusBadge } from "@/components/business/status-badge";
import { TaskActions } from "@/components/business/task-actions";
import { WorkerStatusCard } from "@/components/business/worker-status-card";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkers } from "@/features/components/api/use-workers";
import { useDashboard } from "@/features/dashboard/api/use-dashboard";
import { useTasks } from "@/features/tasks/api/use-tasks";
import { queryKeys } from "@/services/query-keys";
import type { AutomationTask } from "@/types/automation-task";
import { formatBeijingDateTime } from "@/utils/date-time";

function StatCard({
  title,
  value,
  suffix,
}: {
  title: string;
  value: number | string;
  suffix?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="font-medium text-muted-foreground text-sm">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="font-bold text-2xl">
          {value}
          {suffix && (
            <span className="ml-1 font-normal text-muted-foreground text-sm">
              {suffix}
            </span>
          )}
        </p>
      </CardContent>
    </Card>
  );
}

function buildTaskColumns(onUpdate: () => void): ColumnDef<AutomationTask>[] {
  return [
    {
      accessorKey: "title",
      header: "任务标题",
      cell: ({ row }) => (
        <Link
          className="hover:underline"
          params={{ taskId: row.original.id }}
          to="/tasks/$taskId"
        >
          {row.original.title}
        </Link>
      ),
    },
    { accessorKey: "customerName", header: "客户" },
    { accessorKey: "workflowTemplateName", header: "流程模板" },
    { accessorKey: "currentStep", header: "当前步骤" },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    { accessorKey: "owner", header: "负责人" },
    {
      accessorKey: "updatedAt",
      header: "更新时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
    },
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => (
        <TaskActions
          compact
          onUpdate={onUpdate}
          status={row.original.status}
          taskId={row.original.id}
        />
      ),
    },
  ];
}

export function DashboardPage() {
  const queryClient = useQueryClient();
  const onUpdate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });

  const { data: dashboard, isLoading: dashLoading } = useDashboard();
  const { data: tasks = [], isLoading: tasksLoading } = useTasks();
  const { data: workers = [], isLoading: workersLoading } = useWorkers();

  if (dashLoading || tasksLoading || workersLoading) {
    return <MockLoading />;
  }

  const stats = dashboard?.stats ?? {
    pending: 0,
    running: 0,
    waitingHuman: 0,
    failed: 0,
    completedToday: 0,
    successRate: 0,
  };
  const taskTypeDistribution = dashboard?.taskTypeDistribution ?? [];
  const runningTasks = tasks.filter(
    (t) =>
      t.status === "RUNNING" || t.status === "QUEUED" || t.status === "LEASED"
  );
  const humanTasks = tasks.filter((t) => t.status === "WAITING_HUMAN");
  const failedTasks = tasks.filter((t) => t.status === "FAILED");
  const columns = buildTaskColumns(onUpdate);

  return (
    <div className="space-y-6">
      <PageHeader description="自动化任务平台整体运行状态" title="工作台" />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <StatCard title="待执行" value={stats.pending} />
        <StatCard title="运行中" value={stats.running} />
        <StatCard title="待人工" value={stats.waitingHuman} />
        <StatCard title="失败" value={stats.failed} />
        <StatCard title="今日完成" value={stats.completedToday} />
        <StatCard suffix="%" title="成功率" value={stats.successRate} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div>
            <h3 className="mb-3 font-semibold text-lg">当前执行队列</h3>
            <DataTable columns={columns} data={runningTasks} pageSize={5} />
          </div>
          <div>
            <h3 className="mb-3 font-semibold text-lg">待人工处理</h3>
            <DataTable columns={columns} data={humanTasks} pageSize={5} />
          </div>
          <div>
            <h3 className="mb-3 font-semibold text-lg">最近失败任务</h3>
            <DataTable columns={columns} data={failedTasks} pageSize={5} />
          </div>
        </div>
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 font-semibold text-lg">Worker 状态</h3>
            <div className="space-y-3">
              {workers.map((w) => (
                <WorkerStatusCard key={w.id} worker={w} />
              ))}
            </div>
          </div>
          <div>
            <h3 className="mb-3 font-semibold text-lg">任务类型分布</h3>
            <Card>
              <CardContent className="space-y-3 pt-4">
                {taskTypeDistribution.map((item) => (
                  <div className="space-y-1" key={item.taskType}>
                    <div className="flex justify-between text-sm">
                      <span>{item.label}</span>
                      <span className="text-muted-foreground">
                        {item.count}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{
                          width: `${Math.min(100, (item.count / (stats.completedToday || 1)) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
