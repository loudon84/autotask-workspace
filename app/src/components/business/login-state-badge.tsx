import type { PortalLoginState } from "@/types/srm-portal";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/tailwind";

const loginStateConfig: Record<PortalLoginState, { label: string; className: string }> = {
  unknown: { label: "未知", className: "bg-muted text-muted-foreground" },
  valid: { label: "有效", className: "bg-green-500/15 text-green-700 dark:text-green-300" },
  expired: { label: "已过期", className: "bg-red-500/15 text-red-700 dark:text-red-300" },
};

export function LoginStateBadge({ state }: { state: PortalLoginState }) {
  const config = loginStateConfig[state];
  return (
    <Badge variant="outline" className={cn("border-0 font-normal", config.className)}>
      {config.label}
    </Badge>
  );
}
