import { useEffect, useState } from "react";
import { ApiClientError } from "@/actions/autotask-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import {
  useCreatePortalAccount,
  useUpdatePortalAccount,
} from "@/features/srm-portals/api/use-portal-account-mutations";
import type {
  CreatePortalAccountInput,
  PortalAccount,
  PortalStatus,
} from "@/types/portal-account";
import type { ClientOpenMode } from "@/types/web-tab";

type PortalAccountFormDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  portal?: PortalAccount;
};

type FormState = {
  erpEntityCode: string;
  erpEntityName: string;
  portalName: string;
  portalUrl: string;
  loginAccount: string;
  clientOpenMode: ClientOpenMode;
  clientSessionPartition: string;
  credentialRef: string;
  status: PortalStatus;
};

type FieldErrors = Partial<Record<keyof FormState, string>>;

const defaultFormState: FormState = {
  erpEntityCode: "",
  erpEntityName: "",
  portalName: "",
  portalUrl: "",
  loginAccount: "",
  clientOpenMode: "webcontents",
  clientSessionPartition: "",
  credentialRef: "",
  status: "ENABLED",
};

function portalToFormState(portal: PortalAccount): FormState {
  return {
    erpEntityCode: portal.erpEntityCode,
    erpEntityName: portal.erpEntityName,
    portalName: portal.portalName,
    portalUrl: portal.portalUrl,
    loginAccount: portal.loginAccount,
    clientOpenMode: portal.clientOpenMode,
    clientSessionPartition: portal.clientSessionPartition,
    credentialRef: "",
    status: portal.status,
  };
}

function parseFieldErrors(body: unknown): FieldErrors {
  if (!body || typeof body !== "object") {
    return {};
  }

  const errors: FieldErrors = {};
  const record = body as Record<string, unknown>;

  if (Array.isArray(record.detail)) {
    for (const item of record.detail) {
      if (
        item &&
        typeof item === "object" &&
        "loc" in item &&
        "msg" in item
      ) {
        const loc = (item as { loc: unknown[]; msg: string }).loc;
        const field = loc.at(-1);
        if (typeof field === "string" && field in defaultFormState) {
          errors[field as keyof FormState] = (item as { msg: string }).msg;
        }
      }
    }
    return errors;
  }

  for (const [key, value] of Object.entries(record)) {
    if (key in defaultFormState && typeof value === "string") {
      errors[key as keyof FormState] = value;
    }
  }

  return errors;
}

function buildCreateInput(form: FormState): CreatePortalAccountInput {
  const sessionPartition =
    form.clientSessionPartition.trim() ||
    `persist:portal-${form.erpEntityCode.toLowerCase()}`;

  return {
    entityType: "CUSTOMER",
    erpEntityCode: form.erpEntityCode.trim(),
    erpEntityName: form.erpEntityName.trim(),
    portalName: form.portalName.trim(),
    portalUrl: form.portalUrl.trim(),
    loginAccount: form.loginAccount.trim(),
    credentialRef: form.credentialRef.trim(),
    clientOpenMode: form.clientOpenMode,
    clientSessionPartition: sessionPartition,
    status: form.status,
  };
}

export function PortalAccountFormDialog({
  open,
  onOpenChange,
  mode,
  portal,
}: PortalAccountFormDialogProps) {
  const [form, setForm] = useState<FormState>(defaultFormState);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const createMutation = useCreatePortalAccount();
  const updateMutation = useUpdatePortalAccount();

  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (!open) {
      return;
    }
    setFieldErrors({});
    if (mode === "edit" && portal) {
      setForm(portalToFormState(portal));
    } else {
      setForm(defaultFormState);
    }
  }, [open, mode, portal]);

  const updateField = <K extends keyof FormState>(
    key: K,
    value: FormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === "create") {
      createMutation.mutate(buildCreateInput(form), {
        onSuccess: () => onOpenChange(false),
        onError: (err) => {
          if (err instanceof ApiClientError && err.status === 422) {
            setFieldErrors(parseFieldErrors(err.body));
          }
        },
      });
      return;
    }

    if (!portal) {
      return;
    }

    updateMutation.mutate(
      {
        id: portal.id,
        patch: {
          erpEntityCode: form.erpEntityCode.trim(),
          erpEntityName: form.erpEntityName.trim(),
          portalName: form.portalName.trim(),
          portalUrl: form.portalUrl.trim(),
          loginAccount: form.loginAccount.trim(),
          ...(form.credentialRef.trim()
            ? { credentialRef: form.credentialRef.trim() }
            : {}),
          clientOpenMode: form.clientOpenMode,
          clientSessionPartition:
            form.clientSessionPartition.trim() ||
            `persist:portal-${form.erpEntityCode.toLowerCase()}`,
          status: form.status,
        },
      },
      {
        onSuccess: () => onOpenChange(false),
        onError: (err) => {
          if (err instanceof ApiClientError && err.status === 422) {
            setFieldErrors(parseFieldErrors(err.body));
          }
        },
      }
    );
  };

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "新增 SRM" : "编辑 SRM"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "登记门户连接信息和凭据引用，密码不会保存在客户端。"
              : "更新门户连接信息；凭据引用留空时保持现有值。"}
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="erpEntityCode">客户编码 *</Label>
              <Input
                disabled={mode === "edit"}
                id="erpEntityCode"
                onChange={(e) => updateField("erpEntityCode", e.target.value)}
                required
                value={form.erpEntityCode}
              />
              {fieldErrors.erpEntityCode && (
                <p className="text-destructive text-xs">
                  {fieldErrors.erpEntityCode}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="erpEntityName">客户名称 *</Label>
              <Input
                id="erpEntityName"
                onChange={(e) => updateField("erpEntityName", e.target.value)}
                required
                value={form.erpEntityName}
              />
              {fieldErrors.erpEntityName && (
                <p className="text-destructive text-xs">
                  {fieldErrors.erpEntityName}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="portalName">门户名称 *</Label>
            <Input
              id="portalName"
              onChange={(e) => updateField("portalName", e.target.value)}
              required
              value={form.portalName}
            />
            {fieldErrors.portalName && (
              <p className="text-destructive text-xs">{fieldErrors.portalName}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="portalUrl">门户地址 *</Label>
            <Input
              id="portalUrl"
              onChange={(e) => updateField("portalUrl", e.target.value)}
              required
              type="url"
              value={form.portalUrl}
            />
            {fieldErrors.portalUrl && (
              <p className="text-destructive text-xs">{fieldErrors.portalUrl}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="loginAccount">登录账号 *</Label>
            <Input
              id="loginAccount"
              onChange={(e) => updateField("loginAccount", e.target.value)}
              required
              value={form.loginAccount}
            />
            {fieldErrors.loginAccount && (
              <p className="text-destructive text-xs">
                {fieldErrors.loginAccount}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="credentialRef">
              凭据引用（credentialRef）{mode === "create" ? " *" : ""}
            </Label>
            <Input
              id="credentialRef"
              onChange={(e) => updateField("credentialRef", e.target.value)}
              placeholder={
                mode === "create"
                  ? "例如：supplier-portal-phase5-integration"
                  : "留空表示保持现有凭据引用不变"
              }
              required={mode === "create"}
              value={form.credentialRef}
            />
            <p className="text-muted-foreground text-xs">
              仅填写凭据引用标识，不要在此填写门户密码
            </p>
            {fieldErrors.credentialRef && (
              <p className="text-destructive text-xs">
                {fieldErrors.credentialRef}
              </p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>打开方式 *</Label>
              <Select
                onValueChange={(v) =>
                  updateField("clientOpenMode", v as ClientOpenMode)
                }
                value={form.clientOpenMode}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="webcontents">内置 Web</SelectItem>
                  <SelectItem value="system_browser">系统浏览器</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>状态 *</Label>
              <Select
                onValueChange={(v) => updateField("status", v as PortalStatus)}
                value={form.status}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ENABLED">启用</SelectItem>
                  <SelectItem value="DISABLED">禁用</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="clientSessionPartition">Session 分区</Label>
            <Input
              id="clientSessionPartition"
              onChange={(e) =>
                updateField("clientSessionPartition", e.target.value)
              }
              placeholder="留空则自动生成"
              value={form.clientSessionPartition}
            />
            {fieldErrors.clientSessionPartition && (
              <p className="text-destructive text-xs">
                {fieldErrors.clientSessionPartition}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              disabled={isPending}
              onClick={() => onOpenChange(false)}
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
