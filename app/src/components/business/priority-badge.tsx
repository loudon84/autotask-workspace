import type { TaskPriority } from "@/types/automation-task";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/tailwind";

const priorityConfig: Record<TaskPriority, { label: string; className: string }> = {
  low: { label: "低", className: "bg-muted text-muted-foreground" },
  normal: { label: "普通", className: "bg-slate-500/15 text-slate-700 dark:text-slate-300" },
  high: { label: "高", className: "bg-orange-500/15 text-orange-700 dark:text-orange-300" },
  urgent: { label: "紧急", className: "bg-red-500/15 text-red-700 dark:text-red-300" },
};

export function PriorityBadge({ priority }: { priority: TaskPriority }) {
  const config = priorityConfig[priority];
  return (
    <Badge variant="outline" className={cn("border-0 font-normal", config.className)}>
      {config.label}
    </Badge>
  );
}
