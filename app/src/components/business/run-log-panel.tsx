import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { LogLevel, RunLog } from "@/types/task-run";
import { formatBeijingDateTime } from "@/utils/date-time";
import { cn } from "@/utils/tailwind";

const levelColors: Record<LogLevel, string> = {
  INFO: "text-blue-600 dark:text-blue-400",
  WARN: "text-yellow-600 dark:text-yellow-400",
  ERROR: "text-red-600 dark:text-red-400",
  DEBUG: "text-muted-foreground",
};

const allLevels: LogLevel[] = ["INFO", "WARN", "ERROR", "DEBUG"];

export function RunLogPanel({ logs }: { logs: RunLog[] }) {
  const [filter, setFilter] = useState<LogLevel | "ALL">("ALL");
  const filtered =
    filter === "ALL" ? logs : logs.filter((l) => l.level === filter);

  return (
    <div className="flex h-full flex-col rounded-lg border bg-muted/30 font-mono text-xs">
      <div className="flex items-center gap-1 border-b p-2">
        <span className="mr-2 text-muted-foreground">日志级别:</span>
        <Button
          className="h-6 text-xs"
          onClick={() => setFilter("ALL")}
          size="sm"
          variant={filter === "ALL" ? "secondary" : "ghost"}
        >
          全部
        </Button>
        {allLevels.map((level) => (
          <Button
            className="h-6 text-xs"
            key={level}
            onClick={() => setFilter(level)}
            size="sm"
            variant={filter === level ? "secondary" : "ghost"}
          >
            {level}
          </Button>
        ))}
      </div>
      <ScrollArea className="h-[300px] flex-1 p-2">
        {filtered.map((log) => (
          <div className="flex gap-2 py-0.5" key={log.id}>
            <span className="shrink-0 text-muted-foreground">
              {formatBeijingDateTime(log.timestamp)}
            </span>
            <Badge
              className={cn("h-4 px-1 text-[10px]", levelColors[log.level])}
              variant="outline"
            >
              {log.level}
            </Badge>
            <span>{log.message}</span>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="py-4 text-center text-muted-foreground">无日志</p>
        )}
      </ScrollArea>
    </div>
  );
}
