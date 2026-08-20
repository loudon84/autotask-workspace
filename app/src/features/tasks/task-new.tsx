import { useNavigate } from "@tanstack/react-router";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePortalAccounts } from "@/features/srm-portals/api/use-portal-accounts";
import { useCreateTask } from "@/features/tasks/api/use-task-mutations";
import {
  DELIVERY_DATE_TASK_TYPE,
  type ManualDeliveryDateLineInput,
  serializeManualDeliveryDateLines,
  validateManualDeliveryDateLines,
} from "@/features/tasks/delivery-date-task-model";
import { useWorkflowBindings } from "@/features/workflows/api/use-workflow-bindings";
import { useWorkflowTemplates } from "@/features/workflows/api/use-workflow-templates";
import type { TaskPriority } from "@/types/automation-task";

interface ManualDeliveryDateLine extends ManualDeliveryDateLineInput {
  id: string;
}

function createManualDeliveryDateLine(): ManualDeliveryDateLine {
  return {
    id: globalThis.crypto.randomUUID(),
    lineNumber: "",
    materialNumber: "",
  };
}

export function TaskNewPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [portalId, setPortalId] = useState("");
  const [bindingId, setBindingId] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("normal");
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [deliveryDateLines, setDeliveryDateLines] = useState<
    ManualDeliveryDateLine[]
  >([createManualDeliveryDateLine()]);
  const [confirmBeforeRun, setConfirmBeforeRun] = useState(true);
  const [saveScreenshots, setSaveScreenshots] = useState(true);
  const [enableTrace, setEnableTrace] = useState(false);
  const [autoRetry, setAutoRetry] = useState(true);

  const { data: portals = [], isLoading: portalsLoading } = usePortalAccounts();
  const { data: workflows = [], isLoading: workflowsLoading } =
    useWorkflowTemplates();
  const { data: bindings = [], isLoading: bindingsLoading } =
    useWorkflowBindings();

  const selectedPortal = portals.find((p) => p.id === portalId);
  const availableBindings = bindings.filter(
    (binding) =>
      binding.portalAccountId === portalId &&
      binding.status === "enabled" &&
      Boolean(binding.rpaFlowVersionId) &&
      Boolean(binding.flowChecksumSnapshot) &&
      workflows.some(
        (workflow) =>
          workflow.id === binding.workflowTemplateId &&
          workflow.status === "enabled"
      )
  );
  const selectedBinding = availableBindings.find(
    (binding) => binding.id === bindingId
  );
  const selectedWorkflow = workflows.find(
    (workflow) => workflow.id === selectedBinding?.workflowTemplateId
  );
  const isDeliveryDateWorkflow =
    selectedWorkflow?.code === DELIVERY_DATE_TASK_TYPE;

  const createMutation = useCreateTask();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!(title && selectedPortal && selectedBinding && selectedWorkflow)) {
      toast.error("请填写必填字段");
      return;
    }
    if (!(selectedPortal.entityType && selectedPortal.erpEntityCode)) {
      toast.error("所选 Portal 缺少实体类型或 ERP 实体编码");
      return;
    }
    const taskInput: Record<string, unknown> = { ...inputValues };
    if (isDeliveryDateWorkflow) {
      const lineError = validateManualDeliveryDateLines(deliveryDateLines);
      if (lineError) {
        toast.error(lineError);
        return;
      }
      taskInput.order_lines =
        serializeManualDeliveryDateLines(deliveryDateLines);
    }
    createMutation.mutate(
      {
        title,
        taskType: selectedWorkflow.code,
        portalAccountId: selectedPortal.id,
        workflowBindingId: selectedBinding.id,
        entityType: selectedPortal.entityType,
        erpEntityCode: selectedPortal.erpEntityCode,
        erpEntityName: selectedPortal.erpEntityName,
        priority,
        input: taskInput,
      },
      {
        onSuccess: (task) => {
          toast.success("任务已创建");
          navigate({ to: "/tasks/$taskId", params: { taskId: task.id } });
        },
        onError: (error) => {
          toast.error(error instanceof Error ? error.message : "任务创建失败");
        },
      }
    );
  };

  if (portalsLoading || workflowsLoading || bindingsLoading) {
    return <MockLoading />;
  }

  return (
    <form className="mx-auto max-w-2xl space-y-6" onSubmit={handleSubmit}>
      <PageHeader description="创建自动化任务" title="新建任务" />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">基础信息</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">任务名称 *</Label>
            <Input
              id="title"
              onChange={(e) => setTitle(e.target.value)}
              required
              value={title}
            />
          </div>
          <div className="space-y-2">
            <Label>优先级</Label>
            <Select
              onValueChange={(v) => setPriority(v as TaskPriority)}
              value={priority}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">低</SelectItem>
                <SelectItem value="normal">普通</SelectItem>
                <SelectItem value="high">高</SelectItem>
                <SelectItem value="urgent">紧急</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">门户与流程模板</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>门户 *</Label>
            <Select
              onValueChange={(value) => {
                setPortalId(value);
                setBindingId("");
                setInputValues({});
                setDeliveryDateLines([createManualDeliveryDateLine()]);
              }}
              value={portalId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择门户" />
              </SelectTrigger>
              <SelectContent>
                {portals
                  .filter((p) => p.status === "ENABLED")
                  .map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.portalName}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>流程绑定 *</Label>
            <Select
              disabled={!portalId}
              onValueChange={(v) => {
                setBindingId(v);
                setInputValues({});
                setDeliveryDateLines([createManualDeliveryDateLine()]);
              }}
              value={bindingId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择精确版本的流程绑定" />
              </SelectTrigger>
              <SelectContent>
                {availableBindings.map((binding) => {
                  const workflow = workflows.find(
                    (item) => item.id === binding.workflowTemplateId
                  );
                  return (
                    <SelectItem key={binding.id} value={binding.id}>
                      {workflow?.name ?? binding.rpaFlowId} · Flow{" "}
                      {binding.rpaFlowVersion}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            {portalId && availableBindings.length === 0 && (
              <p className="text-destructive text-sm">
                该 Portal 没有已启用且带精确版本快照的流程绑定
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {selectedWorkflow && selectedWorkflow.inputSchema.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">输入参数</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedWorkflow.inputSchema
              .filter(
                (field) =>
                  !(isDeliveryDateWorkflow && field.name === "order_lines")
              )
              .map((field) => (
                <div className="space-y-2" key={field.name}>
                  <Label htmlFor={field.name}>
                    {field.label} {field.required && "*"}
                  </Label>
                  <Input
                    id={field.name}
                    onChange={(e) =>
                      setInputValues((prev) => ({
                        ...prev,
                        [field.name]: e.target.value,
                      }))
                    }
                    required={field.required}
                    value={inputValues[field.name] ?? ""}
                  />
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      {isDeliveryDateWorkflow && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">订单明细 *</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground text-sm">
              推荐先运行任务
              1，由系统自动生成完整明细。手工创建时必须录入门户中的全部订单行，行号和物料号必须精确一致；预计交货日期在任务详情中填写。
            </p>
            <div className="space-y-3">
              {deliveryDateLines.map((line, index) => (
                <div
                  className="grid gap-3 rounded-md border p-3 sm:grid-cols-[5rem_1fr_1fr_auto] sm:items-end"
                  key={line.id}
                >
                  <span className="pb-2 text-muted-foreground text-sm">
                    第 {index + 1} 行
                  </span>
                  <div className="space-y-2">
                    <Label htmlFor={`line-number-${line.id}`}>订单行号 *</Label>
                    <Input
                      id={`line-number-${line.id}`}
                      onChange={(event) =>
                        setDeliveryDateLines((current) =>
                          current.map((item) =>
                            item.id === line.id
                              ? { ...item, lineNumber: event.target.value }
                              : item
                          )
                        )
                      }
                      value={line.lineNumber}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`material-number-${line.id}`}>
                      物料号 *
                    </Label>
                    <Input
                      id={`material-number-${line.id}`}
                      onChange={(event) =>
                        setDeliveryDateLines((current) =>
                          current.map((item) =>
                            item.id === line.id
                              ? { ...item, materialNumber: event.target.value }
                              : item
                          )
                        )
                      }
                      value={line.materialNumber}
                    />
                  </div>
                  <Button
                    aria-label={`删除第 ${index + 1} 行`}
                    onClick={() =>
                      setDeliveryDateLines((current) =>
                        current.filter((item) => item.id !== line.id)
                      )
                    }
                    size="icon"
                    type="button"
                    variant="ghost"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <Button
              onClick={() =>
                setDeliveryDateLines((current) => [
                  ...current,
                  createManualDeliveryDateLine(),
                ])
              }
              type="button"
              variant="outline"
            >
              <Plus className="mr-1 h-4 w-4" />
              添加订单行
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行选项</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label
            className="flex items-center gap-2 text-sm"
            htmlFor="confirm-before-run"
          >
            <Checkbox
              checked={confirmBeforeRun}
              id="confirm-before-run"
              onCheckedChange={(v) => setConfirmBeforeRun(!!v)}
            />
            执行前确认
          </label>
          <label
            className="flex items-center gap-2 text-sm"
            htmlFor="save-screenshots"
          >
            <Checkbox
              checked={saveScreenshots}
              id="save-screenshots"
              onCheckedChange={(v) => setSaveScreenshots(!!v)}
            />
            保存每步截图
          </label>
          <label
            className="flex items-center gap-2 text-sm"
            htmlFor="enable-trace"
          >
            <Checkbox
              checked={enableTrace}
              id="enable-trace"
              onCheckedChange={(v) => setEnableTrace(!!v)}
            />
            开启 Trace
          </label>
          <label
            className="flex items-center gap-2 text-sm"
            htmlFor="auto-retry"
          >
            <Checkbox
              checked={autoRetry}
              id="auto-retry"
              onCheckedChange={(v) => setAutoRetry(!!v)}
            />
            失败自动重试
          </label>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button disabled={createMutation.isPending} type="submit">
          保存任务
        </Button>
        <Button
          onClick={() => navigate({ to: "/tasks" })}
          type="button"
          variant="outline"
        >
          取消
        </Button>
      </div>
    </form>
  );
}
