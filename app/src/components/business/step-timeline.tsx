import type { StepRun } from "@/types/task-run";
import type { WorkflowStep } from "@/types/workflow";
import { cn } from "@/utils/tailwind";
import { CheckCircle2, Circle, Loader2, XCircle, User } from "lucide-react";

type StepItem = WorkflowStep | StepRun;

function getStepStatus(step: StepItem): string {
  if ("status" in step) return step.status;
  return "PENDING";
}

function getStepName(step: StepItem): string {
  if ("stepName" in step) return step.stepName;
  if ("name" in step) return step.name;
  return "";
}

export function StepTimeline({ steps }: { steps: StepItem[] }) {
  return (
    <div className="space-y-0">
      {steps.map((step, index) => {
        const status = getStepStatus(step);
        const isLast = index === steps.length - 1;
        return (
          <div key={"id" in step ? step.id : index} className="flex gap-3">
            <div className="flex flex-col items-center">
              <StepIcon status={status} />
              {!isLast && <div className="w-px flex-1 bg-border my-1 min-h-[24px]" />}
            </div>
            <div className={cn("pb-4", isLast && "pb-0")}>
              <p className="text-sm font-medium">{getStepName(step)}</p>
              {"type" in step && (
                <p className="text-xs text-muted-foreground font-mono">{step.type}</p>
              )}
              {"stepType" in step && (
                <p className="text-xs text-muted-foreground font-mono">{step.stepType}</p>
              )}
              {"message" in step && step.message && (
                <p className="text-xs text-muted-foreground mt-1">{step.message}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "SUCCESS":
      return <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />;
    case "RUNNING":
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin shrink-0" />;
    case "FAILED":
      return <XCircle className="h-5 w-5 text-red-500 shrink-0" />;
    case "WAITING_HUMAN":
      return <User className="h-5 w-5 text-yellow-500 shrink-0" />;
    default:
      return <Circle className="h-5 w-5 text-muted-foreground shrink-0" />;
  }
}
