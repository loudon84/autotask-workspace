import { Link, useNavigate } from "@tanstack/react-router";
import {
  CheckCircle,
  ExternalLink,
  Eye,
  MoreHorizontal,
  Pause,
  Play,
  RotateCcw,
  UserCheck,
  X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { openHumanTask } from "@/actions/web-workspace";
import { HumanConfirmDialog } from "@/components/business/human-checkpoint-panel";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  useCancelTask,
  useMarkHumanOpened,
  useRetryTask,
  useStartTask,
  useUpdateTaskStatus,
} from "@/features/tasks/api/use-task-mutations";
import { useHumanAction } from "@/features/tasks/api/use-tasks";
import { autotaskApi } from "@/services/autotask-api";
import type { AutomationTaskStatus } from "@/types/automation-task";

interface TaskActionsProps {
  compact?: boolean;
  onUpdate?: () => void;
  status: AutomationTaskStatus;
  taskId: string;
}

export function TaskActions({
  taskId,
  status,
  compact,
  onUpdate,
}: TaskActionsProps) {
  const navigate = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [opening, setOpening] = useState(false);

  const startTask = useStartTask();
  const cancelTask = useCancelTask();
  const retryTask = useRetryTask();
  const updateStatus = useUpdateTaskStatus();
  const markHumanOpened = useMarkHumanOpened();

  const { data: humanAction } = useHumanAction(
    taskId,
    status === "WAITING_HUMAN" || status === "HUMAN_OPERATING"
  );

  const handleAction = async (
    action: string,
    newStatus?: AutomationTaskStatus,
    extra?: Record<string, unknown>
  ) => {
    try {
      if (
        newStatus === "RUNNING" &&
        (status === "DRAFT" || status === "READY")
      ) {
        await startTask.mutateAsync(taskId);
      } else if (newStatus === "QUEUED" && status === "FAILED") {
        await retryTask.mutateAsync(taskId);
      } else if (newStatus === "CANCELLED") {
        await cancelTask.mutateAsync(taskId);
      } else if (newStatus) {
        await updateStatus.mutateAsync({ taskId, status: newStatus, extra });
      } else if (extra) {
        await autotaskApi.tasks.update(taskId, extra);
      }
      toast.success(`操作成功: ${action}`);
      onUpdate?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleOpenHuman = async () => {
    if (!humanAction) {
      toast.error("未找到人工动作");
      return;
    }
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
        title: humanAction.instruction.slice(0, 30),
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

  if (compact) {
    return (
      <>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button className="h-8 w-8" size="icon" variant="ghost">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link params={{ taskId }} to="/tasks/$taskId">
                <Eye className="mr-2 h-4 w-4" /> 查看
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {(status === "DRAFT" || status === "READY") && (
              <DropdownMenuItem
                onClick={() =>
                  handleAction("执行", "RUNNING", { progress: 10 })
                }
              >
                <Play className="mr-2 h-4 w-4" /> 执行
              </DropdownMenuItem>
            )}
            {status === "RUNNING" && (
              <DropdownMenuItem
                onClick={() => handleAction("暂停", "WAITING_HUMAN")}
              >
                <Pause className="mr-2 h-4 w-4" /> 暂停
              </DropdownMenuItem>
            )}
            {(status === "WAITING_HUMAN" || status === "HUMAN_OPERATING") && (
              <>
                <DropdownMenuItem disabled={opening} onClick={handleOpenHuman}>
                  <ExternalLink className="mr-2 h-4 w-4" />
                  {status === "HUMAN_OPERATING" ? "重新打开" : "快速打开"}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setConfirmOpen(true)}>
                  <CheckCircle className="mr-2 h-4 w-4" /> 确认已完成
                </DropdownMenuItem>
              </>
            )}
            {status === "FAILED" && (
              <DropdownMenuItem onClick={() => handleAction("重试", "QUEUED")}>
                <RotateCcw className="mr-2 h-4 w-4" /> 重试
              </DropdownMenuItem>
            )}
            {status !== "SUCCESS" &&
              status !== "SUCCESS_MANUAL" &&
              status !== "CANCELLED" && (
                <DropdownMenuItem
                  onClick={() => handleAction("取消", "CANCELLED")}
                >
                  <X className="mr-2 h-4 w-4" /> 取消
                </DropdownMenuItem>
              )}
          </DropdownMenuContent>
        </DropdownMenu>
        {humanAction && (
          <HumanConfirmDialog
            humanActionId={humanAction.id}
            onConfirmed={onUpdate}
            onOpenChange={setConfirmOpen}
            open={confirmOpen}
            taskId={taskId}
          />
        )}
      </>
    );
  }

  return (
    <>
      <div className="flex flex-wrap gap-1">
        <Button asChild size="sm" variant="outline">
          <Link params={{ taskId }} to="/tasks/$taskId">
            <Eye className="mr-1 h-3 w-3" /> 查看
          </Link>
        </Button>

        {(status === "DRAFT" || status === "READY") && (
          <Button
            onClick={() => handleAction("执行", "RUNNING", { progress: 10 })}
            size="sm"
            variant="outline"
          >
            <Play className="mr-1 h-3 w-3" /> 执行
          </Button>
        )}

        {status === "RUNNING" && (
          <>
            <Button asChild size="sm" variant="outline">
              <Link params={{ taskId }} to="/tasks/$taskId">
                查看运行
              </Link>
            </Button>
            <Button
              onClick={() => handleAction("人工接管", "WAITING_HUMAN")}
              size="sm"
              variant="outline"
            >
              <UserCheck className="mr-1 h-3 w-3" /> 人工接管
            </Button>
          </>
        )}

        {(status === "WAITING_HUMAN" || status === "HUMAN_OPERATING") && (
          <>
            <Button
              disabled={opening}
              onClick={handleOpenHuman}
              size="sm"
              variant="outline"
            >
              <ExternalLink className="mr-1 h-3 w-3" />
              {status === "HUMAN_OPERATING" ? "重新打开" : "快速打开"}
            </Button>
            <Button
              onClick={() => setConfirmOpen(true)}
              size="sm"
              variant="outline"
            >
              <CheckCircle className="mr-1 h-3 w-3" /> 确认已完成
            </Button>
          </>
        )}

        {status === "SUCCESS_MANUAL" && (
          <Button asChild size="sm" variant="outline">
            <Link params={{ taskId }} to="/tasks/$taskId">
              查看记录
            </Link>
          </Button>
        )}

        {status === "FAILED" && (
          <>
            <Button
              onClick={() => handleAction("重试", "QUEUED")}
              size="sm"
              variant="outline"
            >
              <RotateCcw className="mr-1 h-3 w-3" /> 重试
            </Button>
            <Button
              onClick={() =>
                handleAction("标记完成", "SUCCESS_MANUAL", { progress: 100 })
              }
              size="sm"
              variant="outline"
            >
              标记完成
            </Button>
          </>
        )}

        {status !== "SUCCESS" &&
          status !== "SUCCESS_MANUAL" &&
          status !== "CANCELLED" &&
          status !== "WAITING_HUMAN" &&
          status !== "HUMAN_OPERATING" && (
            <Button
              onClick={() => handleAction("取消", "CANCELLED")}
              size="sm"
              variant="outline"
            >
              <X className="mr-1 h-3 w-3" /> 取消
            </Button>
          )}
      </div>

      {humanAction && (
        <HumanConfirmDialog
          humanActionId={humanAction.id}
          onConfirmed={onUpdate}
          onOpenChange={setConfirmOpen}
          open={confirmOpen}
          taskId={taskId}
        />
      )}
    </>
  );
}
