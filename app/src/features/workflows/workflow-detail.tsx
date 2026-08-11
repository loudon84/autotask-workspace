import { useNavigate } from "@tanstack/react-router";
import { Power, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { StepTimeline } from "@/components/business/step-timeline";
import { WorkflowStepCard } from "@/components/business/workflow-step-card";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { MockLoading } from "@/components/common/mock-loading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useDeleteWorkflowTemplate,
  useSetWorkflowTemplateStatus,
  useWorkflowTemplate,
} from "@/features/workflows/api/use-workflow-templates";
import { WorkflowTemplateFormDialog } from "@/features/workflows/workflow-template-form-dialog";
import type { WorkflowTemplate } from "@/types/workflow";

function toYaml(workflow: WorkflowTemplate): string {
  const lines = [
    `workflow_id: ${workflow.id}`,
    `name: ${workflow.name}`,
    `version: ${workflow.version}`,
    "steps:",
    ...workflow.steps.map((s) => `  - type: ${s.type}`),
  ];
  return lines.join("\n");
}

function workflowStatusLabel(status: WorkflowTemplate["status"]): string {
  if (status === "enabled") {
    return "启用";
  }
  if (status === "disabled") {
    return "禁用";
  }
  return "草稿";
}

export function WorkflowDetailPage({ workflowId }: { workflowId: string }) {
  const [tab, setTab] = useState("basic");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const navigate = useNavigate();

  const { data: workflow, isLoading } = useWorkflowTemplate(workflowId);
  const statusMutation = useSetWorkflowTemplateStatus();
  const deleteMutation = useDeleteWorkflowTemplate();

  if (isLoading) {
    return <MockLoading />;
  }
  if (!workflow) {
    return <EmptyState title="模板不存在" />;
  }

  const handleStatusChange = async () => {
    const status = workflow.status === "enabled" ? "disabled" : "enabled";
    try {
      await statusMutation.mutateAsync({ workflowId: workflow.id, status });
      toast.success(status === "enabled" ? "模板已启用" : "模板已禁用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "更新模板状态失败");
    }
  };

  const canDelete =
    workflow.status === "draft" || workflow.status === "disabled";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold text-2xl">{workflow.name}</h2>
          <div className="mt-2 flex gap-2">
            <Badge variant="outline">v{workflow.version}</Badge>
            <Badge
              variant={workflow.status === "enabled" ? "default" : "secondary"}
            >
              {workflowStatusLabel(workflow.status)}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <WorkflowTemplateFormDialog workflow={workflow} />
          <Button
            disabled={statusMutation.isPending}
            onClick={handleStatusChange}
            size="sm"
            variant="outline"
          >
            <Power className="mr-1 h-4 w-4" />
            {workflow.status === "enabled" ? "禁用模板" : "启用模板"}
          </Button>
          <Button
            disabled={!canDelete || deleteMutation.isPending}
            onClick={() => setDeleteOpen(true)}
            size="sm"
            title={canDelete ? "删除模板" : "启用中的模板请先禁用"}
            variant="destructive"
          >
            <Trash2 className="mr-1 h-4 w-4" />
            删除模板
          </Button>
        </div>
      </div>

      <ConfirmDialog
        confirmLabel="确认删除"
        description="仅未被任何 Binding 或历史任务引用的草稿、禁用模板可以删除。删除后将从模板列表中移除，且不能通过界面恢复。"
        onConfirm={() => {
          deleteMutation.mutate(workflow.id, {
            onSuccess: () => {
              setDeleteOpen(false);
              navigate({ to: "/workflows" });
            },
          });
        }}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title={`删除模板“${workflow.name}”？`}
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <Tabs
          className="lg:col-span-4"
          onValueChange={setTab}
          orientation="vertical"
          value={tab}
        >
          <div className="flex flex-col gap-4 lg:flex-row">
            <TabsList className="flex h-auto flex-row lg:w-40 lg:flex-col">
              <TabsTrigger value="basic">基础信息</TabsTrigger>
              <TabsTrigger value="input">输入参数</TabsTrigger>
              <TabsTrigger value="steps">步骤配置</TabsTrigger>
              <TabsTrigger value="error">错误处理</TabsTrigger>
              <TabsTrigger value="yaml">Mock YAML</TabsTrigger>
              <TabsTrigger value="test">测试运行</TabsTrigger>
            </TabsList>

            <div className="flex-1">
              <TabsContent value="basic">
                <Card>
                  <CardContent className="space-y-2 pt-4 text-sm">
                    <p>
                      <span className="text-muted-foreground">编码：</span>
                      {workflow.code}
                    </p>
                    <p>
                      <span className="text-muted-foreground">分类：</span>
                      {workflow.category}
                    </p>
                    <p>
                      <span className="text-muted-foreground">实体类型：</span>
                      {workflow.entityType ?? "-"}
                    </p>
                    <p>
                      <span className="text-muted-foreground">目标：</span>
                      {workflow.target}
                    </p>
                    <p>
                      <span className="text-muted-foreground">描述：</span>
                      {workflow.description}
                    </p>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="input">
                <Card>
                  <CardContent className="pt-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-muted-foreground">
                          <th className="pb-2">字段</th>
                          <th className="pb-2">标签</th>
                          <th className="pb-2">类型</th>
                          <th className="pb-2">必填</th>
                        </tr>
                      </thead>
                      <tbody>
                        {workflow.inputSchema.map((f) => (
                          <tr className="border-b" key={f.name}>
                            <td className="py-2 font-mono">{f.name}</td>
                            <td className="py-2">{f.label}</td>
                            <td className="py-2">{f.type}</td>
                            <td className="py-2">{f.required ? "是" : "否"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent className="space-y-4" value="steps">
                <StepTimeline steps={workflow.steps} />
                <div className="grid gap-3 sm:grid-cols-2">
                  {workflow.steps.map((step) => (
                    <WorkflowStepCard key={step.id} step={step} />
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="error">
                <Card>
                  <CardContent className="space-y-3 pt-4">
                    {workflow.steps.map((step) => (
                      <div
                        className="flex justify-between border-b pb-2 text-sm"
                        key={step.id}
                      >
                        <span>{step.name}</span>
                        <Badge variant="outline">
                          {step.onError ?? "fail"}
                        </Badge>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="yaml">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-mono text-sm">
                      Mock YAML
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="overflow-auto rounded-md bg-muted p-4 font-mono text-xs">
                      {toYaml(workflow)}
                    </pre>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="test">
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-muted-foreground text-sm">
                      Mock 测试运行：点击后将模拟执行流程（本阶段不实际运行
                      RPA）。
                    </p>
                  </CardContent>
                </Card>
              </TabsContent>
            </div>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
