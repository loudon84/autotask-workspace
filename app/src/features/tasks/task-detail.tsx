import { useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ArtifactList } from "@/components/business/artifact-preview";
import { HumanCheckpointPanel } from "@/components/business/human-checkpoint-panel";
import { PriorityBadge } from "@/components/business/priority-badge";
import { RunLogPanel } from "@/components/business/run-log-panel";
import { StatusBadge } from "@/components/business/status-badge";
import { StepTimeline } from "@/components/business/step-timeline";
import { TaskActions } from "@/components/business/task-actions";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useArtifactsByTask } from "@/features/artifacts/api/use-artifacts";
import { useRunsByTask } from "@/features/runs/api/use-runs";
import { useAuditLogs, useTask } from "@/features/tasks/api/use-tasks";
import { DeliveryDateTaskEditor } from "@/features/tasks/delivery-date-task-editor";
import { DELIVERY_DATE_TASK_TYPE } from "@/features/tasks/delivery-date-task-model";
import { useWorkflowTemplate } from "@/features/workflows/api/use-workflow-templates";
import { queryKeys } from "@/services/query-keys";
import type { AuditLog } from "@/types/audit-log";
import { formatBeijingDateTime } from "@/utils/date-time";

export function TaskDetailPage({ taskId }: { taskId: string }) {
  const queryClient = useQueryClient();
  const onUpdate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(taskId) });
    queryClient.invalidateQueries({
      queryKey: queryKeys.tasks.humanAction(taskId),
    });
    queryClient.invalidateQueries({ queryKey: ["web-tabs"] });
    queryClient.invalidateQueries({
      queryKey: queryKeys.tasks.auditLogs(taskId),
    });
  };

  const { data: task, isLoading } = useTask(taskId);
  const { data: workflow } = useWorkflowTemplate(
    task?.workflowTemplateId ?? ""
  );
  const { data: runs = [] } = useRunsByTask(taskId);
  const { data: artifacts = [] } = useArtifactsByTask(taskId);
  const { data: auditLogs = [] } = useAuditLogs(taskId);

  if (isLoading) {
    return <MockLoading />;
  }
  if (!task) {
    return <EmptyState title="任务不存在" />;
  }

  const latestRun = runs[0];
  const isDeliveryDateTask = task.taskType === DELIVERY_DATE_TASK_TYPE;
  const auditColumns: ColumnDef<AuditLog>[] = [
    {
      accessorKey: "createdAt",
      header: "时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.createdAt),
    },
    { accessorKey: "action", header: "操作" },
    { accessorKey: "operator", header: "操作人" },
    { accessorKey: "detail", header: "详情" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-bold text-2xl">{task.title}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge
              labelOverride={
                task.status === "DRAFT" && isDeliveryDateTask
                  ? "待填写"
                  : undefined
              }
              status={task.status}
            />
            <PriorityBadge priority={task.priority} />
            <span className="text-muted-foreground text-sm">
              {task.customerName} · {task.owner}
            </span>
          </div>
        </div>
        <TaskActions
          onUpdate={onUpdate}
          status={task.status}
          taskId={task.id}
        />
      </div>

      <HumanCheckpointPanel
        onUpdate={onUpdate}
        status={task.status}
        taskId={task.id}
      />

      {isDeliveryDateTask && (
        <DeliveryDateTaskEditor
          input={task.input}
          onSaved={onUpdate}
          status={task.status}
          taskId={task.id}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">流程步骤</CardTitle>
          </CardHeader>
          <CardContent>
            {workflow ? (
              <StepTimeline steps={workflow.steps} />
            ) : (
              <p className="text-muted-foreground text-sm">无流程信息</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm">运行日志</CardTitle>
          </CardHeader>
          <CardContent>
            {latestRun ? (
              <RunLogPanel logs={latestRun.logs} />
            ) : (
              <p className="text-muted-foreground text-sm">暂无运行记录</p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {!isDeliveryDateTask && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">任务输入参数</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="space-y-2 text-sm">
                  {Object.entries(task.input).map(([key, value]) => (
                    <div className="flex justify-between gap-2" key={key}>
                      <dt className="text-muted-foreground">{key}</dt>
                      <dd className="font-mono">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">关联证据</CardTitle>
            </CardHeader>
            <CardContent>
              <ArtifactList artifacts={artifacts} />
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h3 className="mb-3 font-semibold text-lg">审计日志</h3>
        <DataTable columns={auditColumns} data={auditLogs} pageSize={5} />
      </div>
    </div>
  );
}
