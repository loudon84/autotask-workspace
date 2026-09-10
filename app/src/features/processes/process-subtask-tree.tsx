import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { TaskDetailPage } from "@/features/tasks/task-detail";
import type { ProcessSubTask } from "@/types/process-instance";
import { formatBeijingDateTime } from "@/utils/date-time";

const NODE_ORDER: { taskType: string; label: string }[] = [
  { taskType: "srm_prepare_erp_order", label: "① 建 SDMS" },
  { taskType: "srm_fill_line_delivery_date", label: "② 填写交货日期" },
  { taskType: "srm_sign_order", label: "③ 发起签章" },
  { taskType: "srm_check_reply_status", label: "回签探测" },
  { taskType: "srm_upload_order_attachment", label: "④ 已签章下载上传" },
];

function sortByCreatedDesc(a: ProcessSubTask, b: ProcessSubTask): number {
  return b.createdAt.localeCompare(a.createdAt);
}

function TaskLeaf({
  task,
  onOpen,
}: {
  task: ProcessSubTask;
  onOpen: (taskId: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 py-1 text-sm">
      <button
        className="font-medium text-left text-primary underline underline-offset-4"
        type="button"
        onClick={() => onOpen(task.id)}
      >
        {task.title}
      </button>
      <Badge variant="outline">{task.status}</Badge>
      <span className="text-muted-foreground">
        {formatBeijingDateTime(task.createdAt)}
      </span>
    </div>
  );
}

function HistoryBlock({
  history,
  onOpen,
}: {
  history: ProcessSubTask[];
  onOpen: (taskId: string) => void;
}) {
  if (history.length === 0) {
    return null;
  }
  return (
    <Collapsible className="ml-2 border-muted border-l pl-3">
      <CollapsibleTrigger className="text-muted-foreground flex items-center gap-1 text-xs hover:underline">
        <ChevronDown className="h-3 w-3" />
        历史尝试（{history.length}）
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-1 pt-1">
        {history.map((task) => (
          <TaskLeaf key={task.id} onOpen={onOpen} task={task} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

function NodeGroup({
  label,
  tasks,
  onOpen,
}: {
  label: string;
  tasks: ProcessSubTask[];
  onOpen: (taskId: string) => void;
}) {
  const ordered = [...tasks].sort(sortByCreatedDesc);
  const [latest, ...history] = ordered;
  if (!latest) {
    return null;
  }
  return (
    <div className="space-y-1 rounded-md border p-3">
      <div className="font-medium text-sm">{label}</div>
      <TaskLeaf onOpen={onOpen} task={latest} />
      <HistoryBlock history={history} onOpen={onOpen} />
    </div>
  );
}

function FillLineGroup({
  tasks,
  onOpen,
}: {
  tasks: ProcessSubTask[];
  onOpen: (taskId: string) => void;
}) {
  const byLine = new Map<string, ProcessSubTask[]>();
  for (const task of tasks) {
    const key = task.lineNumber?.trim() || "未知行";
    const bucket = byLine.get(key) ?? [];
    bucket.push(task);
    byLine.set(key, bucket);
  }
  const lineKeys = [...byLine.keys()].sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true })
  );
  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="font-medium text-sm">② 填写交货日期</div>
      {lineKeys.map((lineKey) => {
        const ordered = [...(byLine.get(lineKey) ?? [])].sort(sortByCreatedDesc);
        const [latest, ...history] = ordered;
        if (!latest) {
          return null;
        }
        return (
          <div className="ml-1 space-y-1 border-muted border-l pl-3" key={lineKey}>
            <div className="text-muted-foreground text-xs">行 {lineKey}</div>
            <TaskLeaf onOpen={onOpen} task={latest} />
            <HistoryBlock history={history} onOpen={onOpen} />
          </div>
        );
      })}
    </div>
  );
}

export function ProcessSubTaskTree({
  tasks,
  nodeOrder = NODE_ORDER,
}: {
  tasks: ProcessSubTask[];
  nodeOrder?: { taskType: string; label: string }[];
}) {
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);

  if (tasks.length === 0) {
    return (
      <p className="text-center text-muted-foreground text-sm">暂无子任务</p>
    );
  }

  const knownTypes = new Set(nodeOrder.map((item) => item.taskType));
  const otherTasks = tasks.filter((task) => !knownTypes.has(task.taskType));
  const open = (taskId: string) => setOpenTaskId(taskId);

  return (
    <>
      <div className="space-y-3">
        {nodeOrder.map(({ taskType, label }) => {
          const group = tasks.filter((task) => task.taskType === taskType);
          if (group.length === 0) {
            return null;
          }
          if (taskType === "srm_fill_line_delivery_date") {
            return <FillLineGroup key={taskType} onOpen={open} tasks={group} />;
          }
          return (
            <NodeGroup key={taskType} label={label} onOpen={open} tasks={group} />
          );
        })}
        {otherTasks.length > 0 && (
          <NodeGroup label="其他子任务" onOpen={open} tasks={otherTasks} />
        )}
      </div>
      <Sheet
        open={Boolean(openTaskId)}
        onOpenChange={(next) => {
          if (!next) {
            setOpenTaskId(null);
          }
        }}
      >
        <SheetContent
          className="w-full overflow-y-auto p-6 data-[side=right]:sm:max-w-3xl sm:max-w-3xl"
          side="right"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>任务详情</SheetTitle>
          </SheetHeader>
          {openTaskId ? <TaskDetailPage key={openTaskId} taskId={openTaskId} /> : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
