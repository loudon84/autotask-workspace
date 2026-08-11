import { Progress } from "@/components/ui/progress";

export function ProgressCell({ progress }: { progress: number }) {
  return (
    <div className="flex min-w-[80px] items-center gap-2">
      <Progress value={progress} className="h-2 flex-1" />
      <span className="text-xs text-muted-foreground">{progress}%</span>
    </div>
  );
}
