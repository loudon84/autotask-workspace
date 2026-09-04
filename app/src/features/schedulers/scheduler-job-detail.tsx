import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  useRunSchedulerJobNow,
  useSchedulerJob,
  useSchedulerJobRuns,
  useUpdateSchedulerJob,
} from "@/features/schedulers/api/use-scheduler-jobs";
import type { TimerRun } from "@/features/schedulers/types";
import { CronParseError, cronNextAfter } from "@/features/settings/cron";
import { formatBeijingDateTime } from "@/utils/date-time";

const RUN_STATUS_LABEL: Record<TimerRun["status"], string> = {
  RUNNING: "运行中",
  SUCCESS: "成功",
  FAILED: "失败",
  NO_LISTENER: "无入口",
};

function runBadgeVariant(status: TimerRun["status"]) {
  if (status === "FAILED") {
    return "destructive" as const;
  }
  if (status === "SUCCESS") {
    return "default" as const;
  }
  return "secondary" as const;
}

function runDurationText(run: TimerRun): string {
  if (!run.finishedAt) {
    return "—";
  }
  const ms =
    new Date(run.finishedAt).getTime() - new Date(run.triggeredAt).getTime();
  if (Number.isNaN(ms) || ms < 0) {
    return "—";
  }
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function SchedulerJobDetailPage({ jobId }: { jobId: string }) {
  const { data: job, isLoading } = useSchedulerJob(jobId);
  const { data: runsPage } = useSchedulerJobRuns(jobId);
  const updateMutation = useUpdateSchedulerJob(jobId);
  const runNowMutation = useRunSchedulerJobNow();
  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [cron, setCron] = useState("");

  useEffect(() => {
    if (!job) {
      return;
    }
    setName(job.name);
    setEnabled(job.enabled);
    setCron(job.cron);
  }, [job?.name, job?.enabled, job?.cron]);

  const previewText = useMemo(() => {
    try {
      const next = cronNextAfter(cron.trim() || "* * * * *", new Date());
      const formatted = next.toLocaleString("zh-CN", { hour12: false });
      return enabled ? formatted : `${formatted}（未启用）`;
    } catch (err) {
      return err instanceof CronParseError ? err.message : "表达式无效";
    }
  }, [cron, enabled]);

  const handleSave = () => {
    try {
      cronNextAfter(cron.trim(), new Date());
    } catch (err) {
      toast.error(err instanceof CronParseError ? err.message : "cron 无效");
      return;
    }
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("名称不能为空");
      return;
    }
    updateMutation.mutate(
      { name: trimmedName, enabled, cron: cron.trim() },
      {
        onSuccess: () => toast.success("定时器已保存"),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "保存失败"),
      }
    );
  };

  if (isLoading || !job) {
    return <MockLoading />;
  }

  const runColumns: ColumnDef<TimerRun>[] = [
    {
      accessorKey: "triggeredAt",
      header: "触发时间",
      cell: ({ row }) => formatBeijingDateTime(row.original.triggeredAt),
    },
    {
      accessorKey: "finishedAt",
      header: "结束时间",
      cell: ({ row }) =>
        row.original.finishedAt
          ? formatBeijingDateTime(row.original.finishedAt)
          : "—",
    },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => (
        <Badge variant={runBadgeVariant(row.original.status)}>
          {RUN_STATUS_LABEL[row.original.status] ?? row.original.status}
        </Badge>
      ),
    },
    {
      id: "duration",
      header: "耗时",
      cell: ({ row }) => runDurationText(row.original),
    },
    {
      accessorKey: "error",
      header: "错误",
      cell: ({ row }) => row.original.error ?? "—",
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader description="改名称、开关与 cron" title={job.name} />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">计划</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="timer-name">名称</Label>
            <Input
              id="timer-name"
              onChange={(e) => setName(e.target.value)}
              value={name}
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="job-enabled">启用</Label>
            <Switch
              checked={enabled}
              id="job-enabled"
              onCheckedChange={setEnabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="job-cron">cron</Label>
            <Input
              id="job-cron"
              onChange={(e) => setCron(e.target.value)}
              value={cron}
            />
            <p className="text-muted-foreground text-xs">下次触发：{previewText}</p>
          </div>
          <div className="flex gap-2">
            <Button disabled={updateMutation.isPending} onClick={handleSave}>
              {updateMutation.isPending ? "保存中..." : "保存"}
            </Button>
            <Button
              disabled={runNowMutation.isPending}
              onClick={() =>
                runNowMutation.mutate(jobId, {
                  onSuccess: (result) => {
                    if (result.status === "FAILED") {
                      toast.error(result.message);
                    } else {
                      toast.success(result.message);
                    }
                  },
                  onError: (err) =>
                    toast.error(
                      err instanceof Error ? err.message : "触发失败"
                    ),
                })
              }
              variant="outline"
            >
              {runNowMutation.isPending ? "执行中..." : "立即执行"}
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行记录</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable columns={runColumns} data={runsPage?.items ?? []} />
        </CardContent>
      </Card>
    </div>
  );
}
