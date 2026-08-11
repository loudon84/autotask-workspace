import { Outlet } from "@tanstack/react-router";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getSidebarOpen } from "@/lib/storage";
import { AppSidebar } from "./app-sidebar";
import { PageLayout } from "./page-layout";
import { WebWorkspaceRouteSync } from "./web-workspace-route-sync";

export function AppShell() {
  return (
    <TooltipProvider>
      <SidebarProvider defaultOpen={getSidebarOpen()}>
        <WebWorkspaceRouteSync />
        <AppSidebar />
        <SidebarInset className="flex h-[calc(100vh-2rem)] flex-col overflow-hidden">
          <PageLayout>
            <Outlet />
          </PageLayout>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
