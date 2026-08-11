import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import {
  clearPortalSession,
  openExternal,
  openPortal,
} from "@/actions/web-workspace";
import { ApiClientError } from "@/actions/autotask-api";
import { usePortalWritePermission } from "@/features/srm-portals/hooks/use-portal-write-permission";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { PortalAccount } from "@/types/portal-account";
import { Globe, MoreHorizontal, RotateCcw } from "lucide-react";

type PortalActionsProps = {
  portal: PortalAccount;
  compact?: boolean;
  onUpdate?: () => void;
};

export function PortalActions({ portal, compact, onUpdate }: PortalActionsProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const markForbidden = usePortalWritePermission((s) => s.markForbidden);
  const [resetOpen, setResetOpen] = useState(false);
  const [opening, setOpening] = useState(false);
  const disabled = portal.status !== "ENABLED" || opening;

  const handleOpen = async () => {
    if (portal.status !== "ENABLED") {
      toast.error("门户已禁用，无法打开");
      return;
    }

    setOpening(true);
    try {
      await autotaskApi.portalAccounts.testOpen(portal.id);

      if (portal.clientOpenMode === "system_browser") {
        await openExternal(portal.portalUrl);
        toast.success(`已在外部浏览器打开: ${portal.portalName}`);
        return;
      }

      const tab = await openPortal({
        portalId: portal.id,
        url: portal.portalUrl,
        title: portal.portalName,
        sessionPartition: portal.clientSessionPartition,
        openMode: portal.clientOpenMode,
      });

      toast.success(`已快速打开: ${portal.portalName}`, {
        description: `Tab: ${tab.id}`,
      });
      navigate({ to: "/web-workspace" });
      queryClient.invalidateQueries({
        queryKey: queryKeys.portalAccounts.detail(portal.id),
      });
      onUpdate?.();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 403) {
        markForbidden();
      }
      toast.error(err instanceof Error ? err.message : "打开失败");
    } finally {
      setOpening(false);
    }
  };

  const handleReset = async () => {
    try {
      await clearPortalSession(portal.clientSessionPartition);
      toast.success(`已重置 ${portal.portalName} 的本地登录态`);
      setResetOpen(false);
      onUpdate?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
    }
  };

  if (compact) {
    return (
      <>
        <Button
          disabled={disabled}
          onClick={handleOpen}
          size="sm"
          variant="outline"
        >
          <Globe className="mr-1 h-3 w-3" />
          打开
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="icon" variant="ghost" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setResetOpen(true)}>
              <RotateCcw className="mr-2 h-4 w-4" /> 重置本地登录态
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <ConfirmDialog
          confirmLabel="确认重置"
          description={`确定要重置 ${portal.portalName} 的本地 Session 吗？这将清除已保存的 cookie 和缓存。`}
          onConfirm={handleReset}
          onOpenChange={setResetOpen}
          open={resetOpen}
          title="重置登录态"
        />
      </>
    );
  }

  return (
    <div className="flex flex-wrap gap-1">
      <Button disabled={disabled} onClick={handleOpen} size="sm" variant="outline">
        <Globe className="mr-1 h-3 w-3" />
        {opening ? "打开中..." : "快速打开"}
      </Button>
      <Button onClick={() => setResetOpen(true)} size="sm" variant="outline">
        <RotateCcw className="mr-1 h-3 w-3" /> 重置登录态
      </Button>
      <ConfirmDialog
        confirmLabel="确认重置"
        description={`确定要重置 ${portal.portalName} 的本地 Session 吗？这将清除已保存的 cookie 和缓存。`}
        onConfirm={handleReset}
        onOpenChange={setResetOpen}
        open={resetOpen}
        title="重置登录态"
      />
    </div>
  );
}
