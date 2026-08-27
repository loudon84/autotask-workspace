import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useIntegrationCalls } from "@/features/tasks/api/use-tasks";
import type { IntegrationCallLog } from "@/types/integration-call-log";
import { formatBeijingDateTime } from "@/utils/date-time";
import { cn } from "@/utils/tailwind";

function statusBadgeClass(statusCode?: number | null): string {
  if (statusCode == null) return "text-muted-foreground";
  if (statusCode >= 200 && statusCode < 300) return "text-green-600 dark:text-green-400";
  if (statusCode >= 400 && statusCode < 500) return "text-yellow-600 dark:text-yellow-400";
  if (statusCode >= 500) return "text-red-600 dark:text-red-400";
  return "text-muted-foreground";
}

/** 尝试按 JSON 解析并格式化；非 JSON（如截断的出参、纯文本）原样返回。 */
function formatBody(text?: string | null): string {
  if (!text) return "";
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed === "string") return text;
    return JSON.stringify(parsed, null, 2);
  } catch {
    return text;
  }
}

function CallItem({ call }: { call: IntegrationCallLog }) {
  const [open, setOpen] = useState(false);
  const requestText = useMemo(() => formatBody(call.requestBody), [call.requestBody]);
  const responseText = useMemo(() => formatBody(call.responseBody), [call.responseBody]);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="w-full text-left">
        <div className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded px-1">
          <span className="shrink-0 text-muted-foreground text-xs">
            {formatBeijingDateTime(call.createdAt)}
          </span>
          <Badge className="h-4 px-1 text-[10px]" variant="outline">
            {call.system}
          </Badge>
          <span className="font-mono text-xs font-semibold">{call.method}</span>
          <span
            className={cn(
              "font-mono text-xs",
              statusBadgeClass(call.statusCode)
            )}
          >
            {call.statusCode ?? "—"}
          </span>
          {call.errorCode && (
            <span className="font-mono text-red-600 dark:text-red-400 text-xs">
              {call.errorCode}
            </span>
          )}
          <span className="flex-1 truncate font-mono text-xs text-muted-foreground">
            {call.url}
          </span>
          <span className="shrink-0 text-muted-foreground text-xs">
            {call.durationMs != null ? `${call.durationMs}ms` : ""}
          </span>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-2 border-l-2 border-muted ml-2 pl-3 py-1">
          <div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>入参</span>
              {call.requestTruncated && (
                <Badge className="h-4 px-1 text-[10px]" variant="secondary">
                  已截断
                </Badge>
              )}
            </div>
            <ScrollArea className="h-[120px] rounded border bg-muted/30 p-2">
              <pre className="font-mono text-xs whitespace-pre-wrap break-all">
                {requestText || "—"}
              </pre>
            </ScrollArea>
          </div>
          <div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>出参</span>
              {call.responseTruncated && (
                <Badge className="h-4 px-1 text-[10px]" variant="secondary">
                  已截断
                </Badge>
              )}
            </div>
            <ScrollArea className="h-[160px] rounded border bg-muted/30 p-2">
              <pre className="font-mono text-xs whitespace-pre-wrap break-all">
                {responseText || "—"}
              </pre>
            </ScrollArea>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function IntegrationCallPanel({ taskId }: { taskId: string }) {
  const { data: calls = [], isLoading } = useIntegrationCalls(taskId);

  if (isLoading) {
    return (
      <p className="text-muted-foreground text-sm">加载中…</p>
    );
  }

  if (calls.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">暂无接口调用记录</p>
    );
  }

  return (
    <div className="space-y-0.5">
      {calls.map((call) => (
        <CallItem call={call} key={call.id} />
      ))}
    </div>
  );
}
