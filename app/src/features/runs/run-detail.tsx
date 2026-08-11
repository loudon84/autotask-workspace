import { ArtifactList } from "@/components/business/artifact-preview";
import { RunLogPanel } from "@/components/business/run-log-panel";
import { StatusBadge } from "@/components/business/status-badge";
import { StepTimeline } from "@/components/business/step-timeline";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useArtifactsByRun } from "@/features/artifacts/api/use-artifacts";
import { useRun } from "@/features/runs/api/use-runs";
import { formatBeijingDateTime } from "@/utils/date-time";

export function RunDetailPage({ runId }: { runId: string }) {
  const { data: run, isLoading } = useRun(runId);
  const { data: artifacts = [] } = useArtifactsByRun(runId);

  if (isLoading) {
    return <MockLoading />;
  }
  if (!run) {
    return <EmptyState title="运行记录不存在" />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-bold text-2xl">{run.taskTitle}</h2>
        <div className="mt-2 flex flex-wrap gap-2 text-muted-foreground text-sm">
          <StatusBadge status={run.status} />
          <span>Run: {run.id}</span>
          <span>Worker: {run.workerId}</span>
          <span>开始（北京时间）: {formatBeijingDateTime(run.startedAt)}</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">步骤执行</CardTitle>
          </CardHeader>
          <CardContent>
            <StepTimeline steps={run.stepRuns} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">实时日志</CardTitle>
          </CardHeader>
          <CardContent>
            <RunLogPanel logs={run.logs} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">运行元数据</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">流程模板：</span>
                {run.workflowTemplateName}
              </p>
              <p>
                <span className="text-muted-foreground">任务 ID：</span>
                {run.taskId}
              </p>
              {run.endedAt && (
                <p>
                  <span className="text-muted-foreground">
                    结束（北京时间）：
                  </span>
                  {formatBeijingDateTime(run.endedAt)}
                </p>
              )}
              {run.durationSeconds && (
                <p>
                  <span className="text-muted-foreground">耗时：</span>
                  {run.durationSeconds}s
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">截图 / Artifact</CardTitle>
            </CardHeader>
            <CardContent>
              <ArtifactList artifacts={artifacts} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
