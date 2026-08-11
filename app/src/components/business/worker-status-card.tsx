import type { Worker, WorkerStatus } from "@/types/worker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/tailwind";
import { Cpu, HardDrive, Monitor } from "lucide-react";

const statusConfig: Record<WorkerStatus, { label: string; className: string }> = {
  online: { label: "Online", className: "bg-green-500/15 text-green-700 dark:text-green-300" },
  busy: { label: "Busy", className: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-300" },
  offline: { label: "Offline", className: "bg-muted text-muted-foreground" },
};

export function WorkerStatusCard({ worker }: { worker: Worker }) {
  const config = statusConfig[worker.status];
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{worker.name}</CardTitle>
          <Badge variant="outline">
            {config ? config.label : worker.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <span>当前任务</span>
          <span>{worker.currentTaskCount}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span className="flex items-center gap-1"><Monitor className="h-3 w-3" /> 浏览器</span>
          <span>{worker.browserCount}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span className="flex items-center gap-1"><Cpu className="h-3 w-3" /> CPU</span>
          <span>{worker.cpuUsage}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span className="flex items-center gap-1"><HardDrive className="h-3 w-3" /> 内存</span>
          <span>{worker.memoryUsage}</span>
        </div>
        <p className="text-xs text-muted-foreground pt-1">心跳: {worker.lastHeartbeat}</p>
      </CardContent>
    </Card>
  );
}

export function WorkerStatusBadge({ workers }: { workers: Worker[] }) {
  const online = workers.filter((w) => w.status === "online").length;
  const busy = workers.filter((w) => w.status === "busy").length;
  const offline = workers.filter((w) => w.status === "offline").length;

  return (
    <div className="flex items-center gap-2 text-xs">
      {online > 0 && (
        <Badge variant="outline" className="border-0 bg-green-500/15 text-green-700 dark:text-green-300">
          Online {online}
        </Badge>
      )}
      {busy > 0 && (
        <Badge variant="outline" className="border-0 bg-yellow-500/15 text-yellow-700 dark:text-yellow-300">
          Busy {busy}
        </Badge>
      )}
      {offline > 0 && (
        <Badge variant="outline" className="border-0 bg-muted text-muted-foreground">
          Offline {offline}
        </Badge>
      )}
    </div>
  );
}
