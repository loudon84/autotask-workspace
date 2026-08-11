import { Loader2 } from "lucide-react";

export function MockLoading() {
  return (
    <div className="flex h-48 items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
    </div>
  );
}
