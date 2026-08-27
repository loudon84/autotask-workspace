import { useNavigate } from "@tanstack/react-router";
import { Loader2, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { autotaskApi } from "@/services/autotask-api";
import type { AutomationTask } from "@/types/automation-task";
import type { PortalAccount } from "@/types/portal-account";
import type { TaskRun } from "@/types/task-run";
import type { WorkflowTemplate } from "@/types/workflow";
import { cn } from "@/utils/tailwind";

interface SearchResults {
  portals: PortalAccount[];
  runs: TaskRun[];
  tasks: AutomationTask[];
  workflows: WorkflowTemplate[];
}

function SearchGroup({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-1">
      <div className="px-2 py-1 text-xs font-medium text-muted-foreground">
        {heading}
      </div>
      {children}
    </div>
  );
}

function SearchItem({
  onSelect,
  children,
}: {
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      className={cn(
        "flex w-full items-center rounded-sm px-2 py-1.5 text-left text-xs outline-none",
        "hover:bg-accent hover:text-accent-foreground"
      )}
      onClick={onSelect}
      type="button"
    >
      {children}
    </button>
  );
}

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults(null);
      setOpen(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await autotaskApi.search(q);
        if (!cancelled) {
          setResults(data);
          setOpen(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  const reset = () => {
    setOpen(false);
    setQuery("");
    setResults(null);
  };

  const total = results
    ? results.tasks.length +
      results.workflows.length +
      results.portals.length +
      results.runs.length
    : 0;

  return (
    <div ref={containerRef} className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="h-8 w-48 pl-8 sm:w-64"
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => {
          if (results) {
            setOpen(true);
          }
        }}
        placeholder="搜索任务、流程模板、门户、运行记录..."
        value={query}
      />
      {open && (
        <div className="absolute top-full left-0 z-50 mt-1 max-h-80 w-[28rem] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
          {loading ? (
            <div className="flex items-center justify-center gap-2 px-2 py-6 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              搜索中...
            </div>
          ) : !results || total === 0 ? (
            <div className="px-2 py-6 text-center text-xs text-muted-foreground">
              未找到结果
            </div>
          ) : (
            <>
              {results.tasks.length > 0 && (
                <SearchGroup heading="任务">
                  {results.tasks.map((task) => (
                    <SearchItem
                      key={task.id}
                      onSelect={() => {
                        reset();
                        navigate({
                          to: "/tasks/$taskId",
                          params: { taskId: task.id },
                        });
                      }}
                    >
                      <span className="truncate">{task.title}</span>
                    </SearchItem>
                  ))}
                </SearchGroup>
              )}
              {results.workflows.length > 0 && (
                <SearchGroup heading="流程模板">
                  {results.workflows.map((wf) => (
                    <SearchItem
                      key={wf.id}
                      onSelect={() => {
                        reset();
                        navigate({
                          to: "/workflows/$workflowId",
                          params: { workflowId: wf.id },
                        });
                      }}
                    >
                      <span className="truncate">{wf.name}</span>
                    </SearchItem>
                  ))}
                </SearchGroup>
              )}
              {results.portals.length > 0 && (
                <SearchGroup heading="门户">
                  {results.portals.map((portal) => (
                    <SearchItem
                      key={portal.id}
                      onSelect={() => {
                        reset();
                        navigate({
                          to: "/srm-portals/$portalId",
                          params: { portalId: portal.id },
                        });
                      }}
                    >
                      <span className="truncate">{portal.portalName}</span>
                    </SearchItem>
                  ))}
                </SearchGroup>
              )}
              {results.runs.length > 0 && (
                <SearchGroup heading="运行记录">
                  {results.runs.map((run) => (
                    <SearchItem
                      key={run.id}
                      onSelect={() => {
                        reset();
                        navigate({
                          to: "/runs/$runId",
                          params: { runId: run.id },
                        });
                      }}
                    >
                      <span className="truncate">{run.taskTitle}</span>
                    </SearchItem>
                  ))}
                </SearchGroup>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
