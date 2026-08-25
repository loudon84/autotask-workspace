import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  useSchedulerJob,
  useSchedulerJobTasks,
  useUpdateSchedulerJob,
} from "@/features/schedulers/api/use-scheduler-jobs";
import { CronParseError, cronNextAfter } from "@/features/settings/cron";
import type { SchedulerJobTask } from "@/features/schedulers/types";
import { formatBeijingDateTime } from "@/utils/date-time";

export function SchedulerJobDetailPage({ jobId }: { jobId: string }) {
  const { data: job, isLoading } = useSchedulerJob(jobId);
  const { data: taskPage } = useSchedulerJobTasks(jobId);
  const updateMutation = useUpdateSchedulerJob(jobId);
  const [enabled, setEnabled] = useState(false);
  const [cron, setCron] = useState("");

  useEffect(() => {
    if (!job) {
      return;
    }
    setEnabled(job.enabled);
    setCron(job.cron);
  }, [job]);

  const previewText = useMemo(() => {
    try {
      const next = cronNextAfter(cron.trim() || "* * * * *", new Date());
      const formatted = next.toLocaleString("zh-CN", { hour12: false });
      return enabled ? formatted : `${formatted}（未启用）`;
    } catch (err) {
      return err instanceof CronParseError ? err.message : "表达式无效";
    }
  }, [cron, enabled]);

  const taskColumns: ColumnDef<SchedulerJobTask>[] = [
    {
      accessorKey: "title",
      header: "标题",
      cell: ({ row }) => (
        <Link
          className="text-primary hover:underline"
          params={{ taskId: row.original.id }}
          to="/tasks/$taskId"
        >
          {row.original.title}
        </Link>
      ),
    },
    { accessorKey: "status", header: "状态" },
    {
      accessorKey: "createdAt",
      header: "创建时间",
      cell: ({ row }) => formatBeijingDateTime(row.original.createdAt),
    },
  ];

  const handleSave = () => {
    try {
      cronNextAfter(cron.trim(), new Date());
    } catch (err) {
      toast.error(err instanceof CronParseError ? err.message : "cron 无效");
      return;
    }
    updateMutation.mutate(
      { enabled, cron: cron.trim() },
      {
        onSuccess: () => toast.success("调度任务已保存"),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "保存失败"),
      }
    );
  };

  if (isLoading || !job) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader description={job.portalName} title={job.name} />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">计划</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
          <Button disabled={updateMutation.isPending} onClick={handleSave}>
            {updateMutation.isPending ? "保存中..." : "保存"}
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行任务</CardTitle>
          <p className="text-muted-foreground text-xs">
            到点才会出现任务。回签轮询只处理该门户下待回签/待签章的客户订单；没有候选时列表为空，不代表定时器没跑。
          </p>
        </CardHeader>
        <CardContent>
          <DataTable columns={taskColumns} data={taskPage?.items ?? []} />
        </CardContent>
      </Card>
    </div>
  );
}
