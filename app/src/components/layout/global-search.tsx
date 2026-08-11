import { useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { autotaskApi } from "@/services/autotask-api";
import type { AutomationTask } from "@/types/automation-task";
import type { PortalAccount } from "@/types/portal-account";
import type { TaskRun } from "@/types/task-run";
import type { WorkflowTemplate } from "@/types/workflow";

interface SearchResults {
  portals: PortalAccount[];
  runs: TaskRun[];
  tasks: AutomationTask[];
  workflows: WorkflowTemplate[];
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const navigate = useNavigate();

  const handleSearch = async (value: string) => {
    setQuery(value);
    if (value.length < 1) {
      setResults(null);
      return;
    }
    const data = await autotaskApi.search(value);
    setResults(data);
  };

  return (
    <>
      <Button
        className="relative h-8 w-48 justify-start text-muted-foreground sm:w-64"
        onClick={() => setOpen(true)}
        variant="outline"
      >
        <Search className="mr-2 h-4 w-4" />
        搜索任务、模板...
      </Button>
      <CommandDialog onOpenChange={setOpen} open={open}>
        <CommandInput
          onValueChange={handleSearch}
          placeholder="搜索任务、流程模板、SRM 门户、运行记录..."
          value={query}
        />
        <CommandList>
          <CommandEmpty>未找到结果</CommandEmpty>
          {results && results.tasks.length > 0 && (
            <CommandGroup heading="任务">
              {results.tasks.map((task) => (
                <CommandItem
                  key={task.id}
                  onSelect={() => {
                    setOpen(false);
                    navigate({
                      to: "/tasks/$taskId",
                      params: { taskId: task.id },
                    });
                  }}
                >
                  {task.title}
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {results && results.workflows.length > 0 && (
            <CommandGroup heading="流程模板">
              {results.workflows.map((wf) => (
                <CommandItem
                  key={wf.id}
                  onSelect={() => {
                    setOpen(false);
                    navigate({
                      to: "/workflows/$workflowId",
                      params: { workflowId: wf.id },
                    });
                  }}
                >
                  {wf.name}
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {results && results.portals.length > 0 && (
            <CommandGroup heading="SRM 门户">
              {results.portals.map((portal) => (
                <CommandItem
                  key={portal.id}
                  onSelect={() => {
                    setOpen(false);
                    navigate({
                      to: "/srm-portals/$portalId",
                      params: { portalId: portal.id },
                    });
                  }}
                >
                  {portal.portalName}
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {results && results.runs.length > 0 && (
            <CommandGroup heading="运行记录">
              {results.runs.map((run) => (
                <CommandItem
                  key={run.id}
                  onSelect={() => {
                    setOpen(false);
                    navigate({ to: "/runs/$runId", params: { runId: run.id } });
                  }}
                >
                  {run.taskTitle}
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
