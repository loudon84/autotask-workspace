import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { Eye } from "lucide-react";
import { useState } from "react";
import { listTabs } from "@/actions/web-workspace";
import { StatusBadge } from "@/components/business/status-badge";
import { WorkerStatusCard } from "@/components/business/worker-status-card";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkers } from "@/features/components/api/use-workers";
import { useRuns } from "@/features/runs/api/use-runs";
import type { TaskRun } from "@/types/task-run";
import type { WebTab } from "@/types/web-tab";
import { formatBeijingDateTime } from "@/utils/date-time";

function buildRunColumns(): ColumnDef<TaskRun>[] {
  return [
    { accessorKey: "id", header: "Run ID" },
    {
      accessorKey: "taskTitle",
      header: "任务标题",
      cell: ({ row }) => (
        <Link
          className="hover:underline"
          params={{ taskId: row.original.taskId }}
          to="/tasks/$taskId"
        >
          {row.original.taskTitle}
        </Link>
      ),
    },
    { accessorKey: "workflowTemplateName", header: "流程模板" },
    { accessorKey: "workerId", header: "Worker" },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      id: "currentStep",
      header: "当前步骤",
      cell: ({ row }) => {
        const step = row.original.stepRuns.find(
          (s) => s.stepId === row.original.currentStepId
        );
        return step?.stepName ?? "-";
      },
    },
    {
      accessorKey: "startedAt",
      header: "开始时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.startedAt),
    },
    {
      id: "duration",
      header: "耗时",
      cell: ({ row }) =>
        row.original.durationSeconds
          ? `${Math.floor(row.original.durationSeconds / 60)}m ${row.original.durationSeconds % 60}s`
          : "进行中",
    },
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => (
        <Button asChild size="sm" variant="ghost">
          <Link params={{ runId: row.original.id }} to="/runs/$runId">
            <Eye className="h-4 w-4" />
          </Link>
        </Button>
      ),
    },
  ];
}

function buildWebTabColumns(): ColumnDef<WebTab>[] {
  return [
    { accessorKey: "id", header: "Tab ID" },
    { accessorKey: "title", header: "标题" },
    {
      accessorKey: "url",
      header: "URL",
      cell: ({ row }) => (
        <span className="inline-block max-w-[200px] truncate font-mono text-xs">
          {row.original.url}
        </span>
      ),
    },
    { accessorKey: "sourceType", header: "来源" },
    { accessorKey: "sessionPartition", header: "Session 分区" },
    { accessorKey: "status", header: "状态" },
    {
      accessorKey: "updatedAt",
      header: "更新时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
    },
  ];
}

export function RunsListPage() {
  const [tab, setTab] = useState("queue");

  const { data: runs = [], isLoading: runsLoading } = useRuns();
  const { data: workers = [], isLoading: workersLoading } = useWorkers();
  const { data: webTabs = [], isLoading: tabsLoading } = useQuery({
    queryKey: ["web-tabs"],
    queryFn: listTabs,
  });

  if (runsLoading || workersLoading || tabsLoading) {
    return <MockLoading />;
  }

  const runColumns = buildRunColumns();
  const webTabColumns = buildWebTabColumns();
  const activeRuns = runs.filter(
    (r) =>
      r.status === "RUNNING" || r.status === "QUEUED" || r.status === "LEASED"
  );
  const failedRuns = runs.filter((r) => r.status === "FAILED");

  return (
    <div className="space-y-6">
      <PageHeader
        description="运行队列、Worker 状态、Web 工作区 Tab 与历史记录"
        title="运行监控"
      />

      <Tabs onValueChange={setTab} value={tab}>
        <TabsList>
          <TabsTrigger value="queue">运行队列</TabsTrigger>
          <TabsTrigger value="history">历史运行</TabsTrigger>
          <TabsTrigger value="workers">Worker 状态</TabsTrigger>
          <TabsTrigger value="web-tabs">Web 工作区 Tab</TabsTrigger>
        </TabsList>

        <TabsContent className="mt-4" value="queue">
          <DataTable columns={runColumns} data={activeRuns} pageSize={5} />
        </TabsContent>

        <TabsContent className="mt-4 space-y-6" value="history">
          <DataTable columns={runColumns} data={runs} />
          <div>
            <h3 className="mb-3 font-semibold text-lg">失败重试列表</h3>
            <DataTable columns={runColumns} data={failedRuns} pageSize={5} />
          </div>
        </TabsContent>

        <TabsContent className="mt-4" value="workers">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {workers.map((w) => (
              <WorkerStatusCard key={w.id} worker={w} />
            ))}
          </div>
        </TabsContent>

        <TabsContent className="mt-4" value="web-tabs">
          <DataTable columns={webTabColumns} data={webTabs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
