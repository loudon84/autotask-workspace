import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSchedulerJobs } from "@/features/schedulers/api/use-scheduler-jobs";
import type { SchedulerJob } from "@/features/schedulers/types";
import { formatBeijingDateTime } from "@/utils/date-time";

export function SchedulersListPage() {
  const [enabledFilter, setEnabledFilter] = useState<"all" | "true" | "false">(
    "all"
  );
  const enabledParam =
    enabledFilter === "all" ? undefined : enabledFilter === "true";
  const { data: jobs = [], isLoading } = useSchedulerJobs(enabledParam);

  const columns: ColumnDef<SchedulerJob>[] = useMemo(
    () => [
      {
        accessorKey: "name",
        header: "名称",
        cell: ({ row }) => (
          <Link
            className="font-medium text-primary hover:underline"
            params={{ jobId: row.original.id }}
            to="/schedulers/$jobId"
          >
            {row.original.name}
          </Link>
        ),
      },
      { accessorKey: "portalName", header: "门户" },
      { accessorKey: "cron", header: "cron" },
      {
        accessorKey: "enabled",
        header: "启用",
        cell: ({ row }) => (
          <Badge variant={row.original.enabled ? "default" : "secondary"}>
            {row.original.enabled ? "启用" : "停用"}
          </Badge>
        ),
      },
      {
        accessorKey: "nextRunAt",
        header: "下次触发",
        cell: ({ row }) =>
          row.original.nextRunAt
            ? formatBeijingDateTime(row.original.nextRunAt)
            : "—",
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <PageHeader
        description="由 Binding 保存时自动生成，运维只改开关与 cron"
        title="调度中心"
      />
      <Select
        onValueChange={(value) =>
          setEnabledFilter(value as "all" | "true" | "false")
        }
        value={enabledFilter}
      >
        <SelectTrigger aria-label="按启用状态筛选" className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部</SelectItem>
          <SelectItem value="true">启用</SelectItem>
          <SelectItem value="false">停用</SelectItem>
        </SelectContent>
      </Select>
      {isLoading ? (
        <MockLoading />
      ) : jobs.length === 0 ? (
        <EmptyState description="还没有调度任务。在 Binding JSON 写入 schedule 并保存后会出现在这里。" title="暂无调度任务" />
      ) : (
        <DataTable columns={columns} data={jobs} />
      )}
    </div>
  );
}
