import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  activateTab,
  closeTab,
  copyUrl,
  getActiveTab,
  goBack,
  goForward,
  initWebWorkspace,
  listTabs,
  openExternal,
  openUrl,
  reloadTab,
  setWorkspaceBounds,
  setWorkspaceVisibility,
} from "@/actions/web-workspace";
import { useWebTabUpdates } from "@/hooks/use-web-tab-updates";
import type { WebTab } from "@/types/web-tab";
import { WebEmptyState } from "./web-empty-state";
import { WebTabBar } from "./web-tab-bar";
import { WebToolbar } from "./web-toolbar";

export function WebWorkspacePage() {
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);
  const [addressValue, setAddressValue] = useState("");
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  const { data: tabs = [], refetch } = useQuery({
    queryKey: ["web-tabs"],
    queryFn: listTabs,
  });

  const { data: activeTab } = useQuery({
    queryKey: ["web-active-tab", activeTabId],
    queryFn: getActiveTab,
    enabled: activeTabId !== null,
  });

  const syncBounds = useCallback(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    const rect = el.getBoundingClientRect();
    setWorkspaceBounds({
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height,
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    initWebWorkspace().catch(() => undefined);
    setWorkspaceVisibility(true).catch(() => undefined);
    return () => {
      setWorkspaceVisibility(false).catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    syncBounds();
    const observer = new ResizeObserver(() => syncBounds());
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    window.addEventListener("resize", syncBounds);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", syncBounds);
    };
  }, [syncBounds, tabs.length]);

  useWebTabUpdates(
    useCallback(
      (tab: WebTab) => {
        queryClient.setQueryData<WebTab[]>(["web-tabs"], (prev = []) => {
          const idx = prev.findIndex((t) => t.id === tab.id);
          if (idx === -1) {
            return [...prev, tab];
          }
          const next = [...prev];
          next[idx] = tab;
          return next;
        });
        if (tab.id === activeTabId) {
          setAddressValue(tab.url);
        }
      },
      [queryClient, activeTabId]
    )
  );

  useEffect(() => {
    if (tabs.length > 0 && !activeTabId) {
      const last = tabs[tabs.length - 1];
      if (last) {
        setActiveTabId(last.id);
      }
    }
  }, [tabs, activeTabId]);

  useEffect(() => {
    if (activeTab) {
      setAddressValue(activeTab.url);
    }
  }, [activeTab]);

  const handleActivate = async (tabId: string) => {
    try {
      await activateTab(tabId);
      setActiveTabId(tabId);
      await refetch();
      syncBounds();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "切换 Tab 失败");
    }
  };

  const handleClose = async (tabId: string) => {
    try {
      await closeTab(tabId);
      await refetch();
      const remaining = await listTabs();
      setActiveTabId(
        remaining.length > 0 ? remaining[remaining.length - 1]!.id : null
      );
      syncBounds();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "关闭 Tab 失败");
    }
  };

  const handleNavigate = async (url: string) => {
    try {
      const tab = await openUrl({
        url,
        sourceType: "manual_url",
        sessionPartition: "persist:autotask-global",
      });
      setActiveTabId(tab.id);
      setAddressValue(tab.url);
      await refetch();
      syncBounds();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "打开失败");
    }
  };

  const handleNewTab = () => {
    setAddressValue("");
    toast.info("请在地址栏输入网址");
  };

  const handleCopyUrl = async () => {
    if (!activeTabId) {
      return;
    }
    try {
      const url = await copyUrl(activeTabId);
      await navigator.clipboard.writeText(url);
      toast.success("链接已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <WebTabBar
        activeTabId={activeTabId}
        onActivate={handleActivate}
        onClose={handleClose}
        onNewTab={handleNewTab}
        tabs={tabs}
      />

      <WebToolbar
        activeTab={activeTab ?? null}
        addressValue={addressValue}
        onAddressChange={setAddressValue}
        onBack={() => activeTabId && goBack(activeTabId).then(() => refetch())}
        onClose={() => activeTabId && handleClose(activeTabId)}
        onForward={() =>
          activeTabId && goForward(activeTabId).then(() => refetch())
        }
        onNavigate={handleNavigate}
        onOpenExternal={() => activeTab && openExternal(activeTab.url)}
        onReload={() => activeTabId && reloadTab(activeTabId)}
      />

      <div
        className="relative flex-1 bg-muted/20"
        onContextMenu={(e) => {
          e.preventDefault();
          handleCopyUrl();
        }}
        ref={containerRef}
      >
        {tabs.length === 0 && (
          <WebEmptyState onOpenUrl={() => toast.info("请在地址栏输入网址")} />
        )}
      </div>
    </div>
  );
}
