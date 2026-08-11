import { useNavigate } from "@tanstack/react-router";
import { CheckCircle, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { openHumanTask } from "@/actions/web-workspace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useConfirmHumanAction,
  useMarkHumanOpened,
} from "@/features/tasks/api/use-task-mutations";
import { useHumanAction } from "@/features/tasks/api/use-tasks";
import { autotaskApi } from "@/services/autotask-api";
import type { HumanActionType } from "@/types/human-action";

const typeLabels: Record<HumanActionType, string> = {
  manual_confirm: "人工确认",
  manual_upload: "人工上传",
  manual_approve: "人工审批",
  manual_captcha: "验证码",
  manual_mfa: "MFA 验证",
  manual_exception_handle: "异常处理",
};

interface HumanConfirmDialogProps {
  humanActionId: string;
  onConfirmed?: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  taskId: string;
}

export function HumanConfirmDialog({
  open,
  onOpenChange,
  taskId,
  humanActionId,
  onConfirmed,
}: HumanConfirmDialogProps) {
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);

  const confirmMutation = useConfirmHumanAction();

  const handleConfirm = async () => {
    setLoading(true);
    try {
      const result = await confirmMutation.mutateAsync({
        taskId,
        humanActionId,
        note,
      });
      toast.success("已确认完成", {
        description: `任务状态: ${result.status}。后台不会继续执行同一浏览器会话。`,
      });
      onOpenChange(false);
      setNote("");
      onConfirmed?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "确认失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认人工操作已完成？</DialogTitle>
          <DialogDescription>
            确认后任务将标记为人工完成，后台不会继续执行同一浏览器会话。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label>处理备注（可选）</Label>
          <Textarea
            onChange={(e) => setNote(e.target.value)}
            placeholder="例如：已在客户B供应商平台完成装箱单上传"
            rows={3}
            value={note}
          />
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)} variant="outline">
            取消
          </Button>
          <Button disabled={loading} onClick={handleConfirm}>
            <CheckCircle className="mr-2 h-4 w-4" /> 确认已完成
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface HumanActionPanelProps {
  onUpdate?: () => void;
  status: string;
  taskId: string;
}

export function HumanActionPanel({
  taskId,
  status,
  onUpdate,
}: HumanActionPanelProps) {
  const navigate = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [opening, setOpening] = useState(false);

  const markHumanOpened = useMarkHumanOpened();
  const { data: humanAction } = useHumanAction(taskId);

  if (!humanAction) {
    return null;
  }
  if (
    !["WAITING_HUMAN", "HUMAN_OPERATING", "SUCCESS_MANUAL"].includes(status)
  ) {
    return null;
  }

  const handleOpen = async () => {
    setOpening(true);
    try {
      let sessionPartition = humanAction.portalId
        ? `persist:srm:${humanAction.portalId}`
        : `persist:task:${taskId}`;
      if (humanAction.portalId) {
        const portal = await autotaskApi.portalAccounts.get(
          humanAction.portalId
        );
        if (portal) {
          sessionPartition = portal.clientSessionPartition;
        }
      }

      const tab = await openHumanTask({
        taskId,
        humanActionId: humanAction.id,
        url: humanAction.targetUrl,
        title: typeLabels[humanAction.type],
        portalId: humanAction.portalId,
        sessionPartition,
      });

      await markHumanOpened.mutateAsync({
        taskId,
        humanActionId: humanAction.id,
        clientTabId: tab.id,
      });

      toast.success("已打开待人工处理页面", { description: `Tab: ${tab.id}` });
      navigate({ to: "/web-workspace" });
      onUpdate?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "打开失败");
    } finally {
      setOpening(false);
    }
  };

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(humanAction.targetUrl);
      toast.success("链接已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <>
      <Card className="border-yellow-500/30">
        <CardHeader>
          <CardTitle className="text-sm">人工处理</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">当前状态</dt>
              <dd>{status}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">处理类型</dt>
              <dd>{typeLabels[humanAction.type]}</dd>
            </div>
            <div>
              <dt className="mb-1 text-muted-foreground">处理说明</dt>
              <dd>{humanAction.instruction}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">目标页面</dt>
              <dd className="max-w-[300px] truncate font-mono text-xs">
                {humanAction.targetUrl}
              </dd>
            </div>
            {humanAction.confirmedAt && (
              <>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">确认人</dt>
                  <dd>{humanAction.confirmedBy ?? "-"}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">确认时间</dt>
                  <dd>{humanAction.confirmedAt}</dd>
                </div>
                {humanAction.note && (
                  <div>
                    <dt className="mb-1 text-muted-foreground">确认备注</dt>
                    <dd>{humanAction.note}</dd>
                  </div>
                )}
              </>
            )}
          </dl>

          {(status === "WAITING_HUMAN" || status === "HUMAN_OPERATING") && (
            <div className="flex flex-wrap gap-2">
              <Button disabled={opening} onClick={handleOpen} size="sm">
                <ExternalLink className="mr-2 h-4 w-4" />
                {status === "HUMAN_OPERATING" ? "重新打开" : "快速打开"}
              </Button>
              <Button onClick={handleCopyUrl} size="sm" variant="outline">
                <Copy className="mr-2 h-4 w-4" /> 复制链接
              </Button>
              <Button
                onClick={() => setConfirmOpen(true)}
                size="sm"
                variant="outline"
              >
                <CheckCircle className="mr-2 h-4 w-4" /> 确认已完成
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <HumanConfirmDialog
        humanActionId={humanAction.id}
        onConfirmed={onUpdate}
        onOpenChange={setConfirmOpen}
        open={confirmOpen}
        taskId={taskId}
      />
    </>
  );
}

export function getHumanActionTypeLabel(type: HumanActionType): string {
  return typeLabels[type];
}

// Backward-compatible exports
export { HumanActionPanel as HumanCheckpointPanel };
export function getReasonLabel(type: HumanActionType): string {
  return typeLabels[type];
}
