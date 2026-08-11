import type { WorkflowStep } from "@/types/workflow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function WorkflowStepCard({ step }: { step: WorkflowStep }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{step.name}</CardTitle>
          <Badge variant="outline" className="font-mono text-xs">{step.type}</Badge>
        </div>
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground space-y-1">
        {step.description && <p>{step.description}</p>}
        <div className="flex gap-4">
          {step.timeout !== undefined && <span>超时: {step.timeout}s</span>}
          {step.retry !== undefined && <span>重试: {step.retry}</span>}
          {step.onError && <span>错误: {step.onError}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
