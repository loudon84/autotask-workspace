import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WebTab } from "@/types/web-tab";
import { cn } from "@/utils/tailwind";

type WebTabBarProps = {
  tabs: WebTab[];
  activeTabId: string | null;
  onActivate: (tabId: string) => void;
  onClose: (tabId: string) => void;
  onNewTab: () => void;
};

export function WebTabBar({
  tabs,
  activeTabId,
  onActivate,
  onClose,
  onNewTab,
}: WebTabBarProps) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-b bg-muted/30 px-2 py-1">
      {tabs.map((tab) => (
        <div
          className={cn(
            "group flex max-w-[200px] shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs",
            activeTabId === tab.id
              ? "bg-background shadow-sm"
              : "hover:bg-background/60"
          )}
          key={tab.id}
        >
          <button
            className="flex min-w-0 flex-1 items-center gap-1"
            onClick={() => onActivate(tab.id)}
            type="button"
          >
            {tab.favicon ? (
              <img alt="" className="h-3 w-3 shrink-0" src={tab.favicon} />
            ) : (
              <span className="h-3 w-3 shrink-0 rounded-full bg-muted" />
            )}
            <span className="truncate">{tab.title}</span>
            {tab.status === "loading" && (
              <span className="text-muted-foreground">...</span>
            )}
          </button>
          <button
            className="opacity-0 group-hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              onClose(tab.id);
            }}
            type="button"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
      <Button
        className="h-7 w-7 shrink-0"
        onClick={onNewTab}
        size="icon"
        variant="ghost"
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
}
