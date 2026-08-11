import type { PortalAccount } from "@/types/portal-account";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const openModeLabels = {
  webcontents: "内置 Web",
  system_browser: "系统浏览器",
} as const;

export function SrmPortalCard({ portal }: { portal: PortalAccount }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{portal.portalName}</CardTitle>
          <Badge
            variant={portal.status === "ENABLED" ? "default" : "secondary"}
          >
            {portal.status === "ENABLED" ? "启用" : "禁用"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-1 text-muted-foreground text-sm">
        <p>{portal.erpEntityName}</p>
        <p className="truncate font-mono text-xs">{portal.portalUrl}</p>
        <p>{openModeLabels[portal.clientOpenMode]}</p>
      </CardContent>
    </Card>
  );
}
