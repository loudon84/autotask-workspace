import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  SOP_MAIN_STEPS,
  sopProgressIndex,
} from "@/features/statements/statement-model";
import type { StatementSopStepId } from "@/types/statement";

export function StatementSopProgress({
  currentStep,
  cancelled = false,
}: {
  currentStep: StatementSopStepId | string;
  cancelled?: boolean;
}) {
  const currentIndex = sopProgressIndex(currentStep);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {SOP_MAIN_STEPS.map((step, index) => {
        const reached = currentIndex >= index;
        const isCurrent = currentIndex === index && !cancelled;
        return (
          <div className="flex items-center gap-2" key={step.id}>
            {index > 0 && <div className="h-px w-6 bg-border" />}
            <div
              className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${
                isCurrent
                  ? "border-primary text-primary"
                  : reached
                    ? "border-primary/40 text-foreground"
                    : "text-muted-foreground"
              }`}
            >
              {reached && !isCurrent && <Check className="h-3 w-3" />}
              {step.name}
            </div>
          </div>
        );
      })}
      {cancelled ? (
        <Badge variant="outline">已作废</Badge>
      ) : null}
    </div>
  );
}
