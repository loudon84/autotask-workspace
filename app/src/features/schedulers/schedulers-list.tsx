import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  useRunSchedulerJobNow,
  useSchedulerJobs,
} from "@/features/schedulers/api/use-scheduler-jobs";
import type { Timer } from "@/features/schedulers/types";

import { formatBeijingDateTime } from "@/utils/date-time";

function RunNowButton({ job }: { job: Timer }) {
  const runNow = useRunSchedulerJobNow();
  return (
    <Button
      disabled={runNow.isPending}
      onClick={() =>
        runNow.mutate(job.id, {
          onSuccess: (result) => {
            if (result.status === "FAILED") {
              toast.error(result.message);
            } else {
              toast.success(result.message);
            }
          },
          onError: (error) => toast.error(`触发失败：${error.message}`),
        })
      }
      size="sm"
      variant="outline"
    >
      立即执行
    </Button>
  );
}

export function SchedulersListPage() {
  const [enabledFilter, setEnabledFilter] = useState<"all" | "true" | "false">(
    "all"
  );
  const enabledParam =
    enabledFilter === "all" ? undefined : enabledFilter === "true";
  const { data: jobs = [], isLoading } = useSchedulerJobs(enabledParam);

  const columns: ColumnDef<Timer>[] = useMemo(
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
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => <RunNowButton job={row.original} />,
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <PageHeader

        description="维护定时器的名称、开关与 cron。到点通知已登记的入口。"
        title="调度中心"
      />
      <TenantSchedulerCard />
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
        <EmptyState
          description="还没有定时器。任务登记后会出现在这里。"
          title="暂无定时器"
        />
      ) : (
        <DataTable columns={columns} data={jobs} />
      )}
    </div>
  );
}
