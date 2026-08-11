import { Pencil, Plus, Power } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateWorkflowBinding,
  useSetWorkflowBindingStatus,
  useUpdateWorkflowBinding,
  useWorkflowBindings,
} from "@/features/workflows/api/use-workflow-bindings";
import { useWorkflowTemplates } from "@/features/workflows/api/use-workflow-templates";
import type { PortalAccount } from "@/types/portal-account";
import type { WorkflowTemplate } from "@/types/workflow";
import type {
  CreateWorkflowBindingInput,
  WorkflowBinding,
} from "@/types/workflow-binding";

interface WorkflowBindingManagerProps {
  portal: PortalAccount;
}

export function WorkflowBindingManager({
  portal,
}: WorkflowBindingManagerProps) {
  const { data: allBindings = [], isLoading: bindingsLoading } =
    useWorkflowBindings();
  const { data: workflows = [], isLoading: workflowsLoading } =
    useWorkflowTemplates();
  const statusMutation = useSetWorkflowBindingStatus();
  const bindings = allBindings.filter(
    (binding) => binding.portalAccountId === portal.id
  );
  const workflowMap = useMemo(
    () => new Map(workflows.map((workflow) => [workflow.id, workflow])),
    [workflows]
  );

  const handleStatusChange = async (binding: WorkflowBinding) => {
    const status = binding.status === "enabled" ? "disabled" : "enabled";
    try {
      await statusMutation.mutateAsync({ bindingId: binding.id, status });
      toast.success(status === "enabled" ? "Binding 已启用" : "Binding 已禁用");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "更新 Binding 状态失败"
      );
    }
  };

  if (bindingsLoading || workflowsLoading) {
    return <p className="text-muted-foreground text-sm">正在加载 Binding...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-base">工作流绑定</h3>
          <p className="text-muted-foreground text-sm">
            将此 Portal、Task 模板和已发布的 Engine Flow 精确版本绑定。
          </p>
        </div>
        <WorkflowBindingDialog portal={portal} workflows={workflows} />
      </div>

      {bindings.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground text-sm">
            当前 Portal 还没有 Binding。请先确保模板已启用、Flow 已在 Engine
            发布。
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {bindings.map((binding) => {
            const workflow = workflowMap.get(binding.workflowTemplateId);
            return (
              <Card key={binding.id}>
                <CardHeader className="flex-row items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">
                      {workflow?.name ?? binding.workflowTemplateId}
                    </CardTitle>
                    <p className="mt-1 font-mono text-muted-foreground text-xs">
                      {binding.rpaFlowId}@{binding.rpaFlowVersion}
                    </p>
                  </div>
                  <Badge
                    variant={
                      binding.status === "enabled" ? "default" : "secondary"
                    }
                  >
                    {binding.status === "enabled" ? "已启用" : "已禁用"}
                  </Badge>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-2 text-sm sm:grid-cols-2">
                    <BindingField
                      label="模板版本"
                      value={binding.workflowTemplateVersion}
                    />
                    <BindingField
                      label="Engine 类型"
                      value={binding.rpaEngineType}
                    />
                    <BindingField
                      label="精确 Flow Version UUID"
                      value={binding.rpaFlowVersionId ?? "未固化"}
                    />
                    <BindingField
                      label="Package checksum"
                      value={binding.flowChecksumSnapshot ?? "未固化"}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <WorkflowBindingDialog
                      binding={binding}
                      portal={portal}
                      workflows={workflows}
                    />
                    <Button
                      disabled={statusMutation.isPending}
                      onClick={() => handleStatusChange(binding)}
                      size="sm"
                      variant="outline"
                    >
                      <Power className="mr-1 h-4 w-4" />
                      {binding.status === "enabled" ? "禁用" : "启用"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function BindingField({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="truncate font-mono text-xs" title={value}>
        {value}
      </p>
    </div>
  );
}

interface WorkflowBindingDialogProps {
  binding?: WorkflowBinding;
  portal: PortalAccount;
  workflows: WorkflowTemplate[];
}

type BindingForm = Omit<CreateWorkflowBindingInput, "config"> & {
  configJson: string;
};

function defaultConfig(portal: PortalAccount): Record<string, unknown> {
  return {
    portalUrl: portal.portalUrl,
    browserSession: {
      mode: "MANAGED",
      headless: true,
      channel: "chrome",
      profileRef: null,
      cdpEndpointRef: null,
      closePolicy: "CLOSE_ON_FINISH",
    },
  };
}

function initialBindingForm(
  portal: PortalAccount,
  binding?: WorkflowBinding
): BindingForm {
  return {
    portalAccountId: portal.id,
    workflowTemplateId: binding?.workflowTemplateId ?? "",
    workflowTemplateVersion: binding?.workflowTemplateVersion ?? "",
    rpaEngineType: binding?.rpaEngineType ?? "PLAYWRIGHT_CDP",
    rpaFlowId: binding?.rpaFlowId ?? "",
    rpaFlowVersion: binding?.rpaFlowVersion ?? "",
    status: binding?.status ?? "enabled",
    configJson: JSON.stringify(
      binding?.config ?? defaultConfig(portal),
      null,
      2
    ),
  };
}

function WorkflowBindingDialog({
  binding,
  portal,
  workflows,
}: WorkflowBindingDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<BindingForm>(() =>
    initialBindingForm(portal, binding)
  );
  const createMutation = useCreateWorkflowBinding();
  const updateMutation = useUpdateWorkflowBinding();
  const enabledWorkflows = workflows.filter(
    (workflow) =>
      workflow.status === "enabled" ||
      workflow.id === binding?.workflowTemplateId
  );
  const isEditing = Boolean(binding);
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (open) {
      setForm(initialBindingForm(portal, binding));
    }
  }, [binding, open, portal]);

  const selectWorkflow = (workflowId: string) => {
    const workflow = workflows.find((item) => item.id === workflowId);
    setForm((current) => ({
      ...current,
      workflowTemplateId: workflowId,
      workflowTemplateVersion: workflow?.version ?? "",
      rpaFlowId: current.rpaFlowId || `rpa_flow_${workflow?.code ?? ""}`,
      rpaFlowVersion: current.rpaFlowVersion || workflow?.version || "",
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (
      [
        form.workflowTemplateId,
        form.workflowTemplateVersion,
        form.rpaFlowId,
        form.rpaFlowVersion,
      ].some((value) => !value.trim())
    ) {
      toast.error("请填写所有必填字段");
      return;
    }

    let config: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(form.configJson);
      if (!isObject(parsed)) {
        throw new Error("Binding config 必须是 JSON 对象");
      }
      const browserSession = parsed.browserSession;
      if (!isObject(browserSession) || browserSession.mode !== "MANAGED") {
        toast.error("config.browserSession.mode 必须为 MANAGED");
        return;
      }
      config = parsed;
    } catch {
      toast.error("Binding config 必须是有效的 JSON 对象");
      return;
    }

    try {
      if (binding) {
        await updateMutation.mutateAsync({
          bindingId: binding.id,
          input: {
            workflowTemplateVersion: form.workflowTemplateVersion,
            rpaEngineType: form.rpaEngineType,
            rpaFlowId: form.rpaFlowId,
            rpaFlowVersion: form.rpaFlowVersion,
            status: form.status,
            config,
          },
        });
        toast.success("Binding 已更新并重新校验精确 Flow 版本");
      } else {
        await createMutation.mutateAsync({
          portalAccountId: portal.id,
          workflowTemplateId: form.workflowTemplateId,
          workflowTemplateVersion: form.workflowTemplateVersion,
          rpaEngineType: form.rpaEngineType,
          rpaFlowId: form.rpaFlowId,
          rpaFlowVersion: form.rpaFlowVersion,
          status: form.status,
          config,
        });
        toast.success("Binding 已创建并固化精确 Flow 版本");
      }
      setOpen(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "保存 Workflow Binding 失败"
      );
    }
  };

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button size="sm" variant={isEditing ? "outline" : "default"}>
          {isEditing ? (
            <Pencil className="mr-1 h-4 w-4" />
          ) : (
            <Plus className="mr-1 h-4 w-4" />
          )}
          {isEditing ? "编辑 Binding" : "新建 Binding"}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "编辑 Workflow Binding" : "新建 Workflow Binding"}
          </DialogTitle>
          <DialogDescription>
            Task 会调用 Engine 校验 Flow ID 与版本，并保存精确 UUID 和
            checksum。
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <FormField label="工作流模板" required>
            <Select
              disabled={isEditing}
              onValueChange={selectWorkflow}
              value={form.workflowTemplateId}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择已启用模板" />
              </SelectTrigger>
              <SelectContent>
                {enabledWorkflows.map((workflow) => (
                  <SelectItem key={workflow.id} value={workflow.id}>
                    {workflow.name} · {workflow.version}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="模板版本" required>
            <Input readOnly value={form.workflowTemplateVersion} />
          </FormField>
          <FormField label="Engine 类型" required>
            <Input readOnly value={form.rpaEngineType} />
          </FormField>
          <FormField label="状态" required>
            <Select
              onValueChange={(value) =>
                setForm((current) => ({
                  ...current,
                  status: value as WorkflowBinding["status"],
                }))
              }
              value={form.status}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="enabled">启用</SelectItem>
                <SelectItem value="disabled">禁用</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Flow ID" required>
            <Input
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rpaFlowId: event.target.value,
                }))
              }
              placeholder="rpa_flow_srm_fetch_po"
              value={form.rpaFlowId}
            />
          </FormField>
          <FormField label="Flow 版本" required>
            <Input
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rpaFlowVersion: event.target.value,
                }))
              }
              placeholder="1.1.0"
              value={form.rpaFlowVersion}
            />
          </FormField>
          <FormField
            className="sm:col-span-2"
            label="Binding config JSON"
            required
          >
            <Textarea
              className="min-h-64 font-mono text-xs"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  configJson: event.target.value,
                }))
              }
              value={form.configJson}
            />
          </FormField>
          <DialogFooter className="sm:col-span-2">
            <Button
              disabled={isPending}
              onClick={() => setOpen(false)}
              type="button"
              variant="outline"
            >
              取消
            </Button>
            <Button disabled={isPending} type="submit">
              {isPending ? "校验并保存中..." : "校验并保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function FormField({
  children,
  className,
  label,
  required,
}: {
  children: React.ReactNode;
  className?: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label>
        {label}
        {required ? " *" : ""}
      </Label>
      {children}
    </div>
  );
}
