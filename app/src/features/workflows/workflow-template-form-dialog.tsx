import { Pencil, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
  useCreateWorkflowTemplate,
  useUpdateWorkflowTemplate,
} from "@/features/workflows/api/use-workflow-templates";
import type {
  CreateWorkflowTemplateInput,
  WorkflowTemplate,
} from "@/types/workflow";

interface WorkflowTemplateFormDialogProps {
  workflow?: WorkflowTemplate;
}

type TemplateForm = Omit<
  CreateWorkflowTemplateInput,
  "inputSchema" | "businessSteps"
> & {
  businessStepsJson: string;
  inputSchemaJson: string;
};

function initialForm(workflow?: WorkflowTemplate): TemplateForm {
  if (workflow) {
    return {
      name: workflow.name,
      code: workflow.code,
      description: workflow.description,
      entityType: workflow.entityType ?? "CUSTOMER",
      category: workflow.category,
      status: workflow.status,
      version: workflow.version,
      inputSchemaJson: JSON.stringify(workflow.inputSchema, null, 2),
      businessStepsJson: JSON.stringify(workflow.steps, null, 2),
    };
  }
  return {
    name: "",
    code: "",
    description: "",
    entityType: "CUSTOMER",
    category: "",
    status: "draft",
    version: "1.0.0",
    inputSchemaJson: JSON.stringify(
      [
        {
          name: "po_no",
          type: "string",
          required: true,
        },
      ],
      null,
      2
    ),
    businessStepsJson: "[]",
  };
}

function parseArray(
  value: string,
  fieldName: string
): Record<string, unknown>[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${fieldName} 不是有效的 JSON`);
  }
  if (!Array.isArray(parsed) || parsed.some((item) => !isObject(item))) {
    throw new Error(`${fieldName} 必须是 JSON 对象数组`);
  }
  return parsed;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function WorkflowTemplateFormDialog({
  workflow,
}: WorkflowTemplateFormDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TemplateForm>(() => initialForm(workflow));
  const createMutation = useCreateWorkflowTemplate();
  const updateMutation = useUpdateWorkflowTemplate();
  const isEditing = Boolean(workflow);
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (open) {
      setForm(initialForm(workflow));
    }
  }, [open, workflow]);

  const updateField = <K extends keyof TemplateForm>(
    field: K,
    value: TemplateForm[K]
  ) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (
      [form.name, form.code, form.category, form.version].some(
        (value) => !value.trim()
      )
    ) {
      toast.error("请填写所有必填字段");
      return;
    }

    try {
      const inputSchema = parseArray(form.inputSchemaJson, "输入参数");
      const businessSteps = parseArray(form.businessStepsJson, "业务步骤");
      if (workflow) {
        await updateMutation.mutateAsync({
          workflowId: workflow.id,
          input: {
            name: form.name,
            description: form.description,
            entityType: form.entityType,
            category: form.category,
            version: form.version,
            inputSchema,
            businessSteps,
          },
        });
        toast.success("工作流模板已更新");
      } else {
        await createMutation.mutateAsync({
          name: form.name,
          code: form.code,
          description: form.description,
          entityType: form.entityType,
          category: form.category,
          status: "draft",
          version: form.version,
          inputSchema,
          businessSteps,
        });
        toast.success("工作流模板已创建，请确认配置后启用");
      }
      setOpen(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "保存工作流模板失败"
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
          {isEditing ? "编辑模板" : "新建模板"}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "编辑工作流模板" : "新建工作流模板"}
          </DialogTitle>
          <DialogDescription>
            模板描述业务输入与步骤，不上传 Flow 包；创建后请在详情页单独启用。
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <FormField label="模板名称" required>
            <Input
              onChange={(event) => updateField("name", event.target.value)}
              value={form.name}
            />
          </FormField>
          <FormField label="模板编码" required>
            <Input
              disabled={isEditing}
              onChange={(event) => updateField("code", event.target.value)}
              placeholder="srm_fetch_po"
              value={form.code}
            />
          </FormField>
          <FormField label="实体类型" required>
            <Select
              onValueChange={(value) => updateField("entityType", value)}
              value={form.entityType}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CUSTOMER">客户</SelectItem>
                <SelectItem value="SUPPLIER">供应商</SelectItem>
                <SelectItem value="BOTH">客户与供应商</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="分类" required>
            <Input
              onChange={(event) => updateField("category", event.target.value)}
              placeholder="procurement"
              value={form.category}
            />
          </FormField>
          <FormField label="模板版本" required>
            <Input
              onChange={(event) => updateField("version", event.target.value)}
              placeholder="1.0.0"
              value={form.version}
            />
          </FormField>
          <FormField label="描述">
            <Input
              onChange={(event) =>
                updateField("description", event.target.value)
              }
              value={form.description ?? ""}
            />
          </FormField>
          <FormField className="sm:col-span-2" label="输入参数 JSON" required>
            <Textarea
              className="min-h-40 font-mono text-xs"
              onChange={(event) =>
                updateField("inputSchemaJson", event.target.value)
              }
              value={form.inputSchemaJson}
            />
          </FormField>
          <FormField className="sm:col-span-2" label="业务步骤 JSON" required>
            <Textarea
              className="min-h-40 font-mono text-xs"
              onChange={(event) =>
                updateField("businessStepsJson", event.target.value)
              }
              value={form.businessStepsJson}
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
              {isPending ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
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
