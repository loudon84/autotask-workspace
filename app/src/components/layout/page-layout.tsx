import { useLocation } from "@tanstack/react-router";
import { BackendStatusBadges } from "@/components/business/backend-status-badges";
import { WorkerStatusBadge } from "@/components/business/worker-status-card";
import ToggleTheme from "@/components/toggle-theme";
import { useWorkers } from "@/features/components/api/use-workers";
import { AppHeader } from "./app-header";
import { getPageTitle } from "./data/sidebar-data";
import { GlobalSearch } from "./global-search";

export function PageLayout({ children }: { children: React.ReactNode }) {
  const pathname = useLocation({ select: (l) => l.pathname });
  const title = getPageTitle(pathname);

  const { data: workers = [] } = useWorkers();

  return (
    <div className="flex h-full flex-col">
      <AppHeader title={title}>
        <GlobalSearch />
        <BackendStatusBadges />
        <WorkerStatusBadge workers={workers} />
        <ToggleTheme />
      </AppHeader>
      <div className="flex-1 overflow-auto p-4">{children}</div>
    </div>
  );
}
