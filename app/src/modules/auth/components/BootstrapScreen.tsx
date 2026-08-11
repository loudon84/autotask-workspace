import { Loader2 } from "lucide-react";

export function BootstrapScreen() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="text-muted-foreground text-sm">正在初始化...</p>
    </div>
  );
}
