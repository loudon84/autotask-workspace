import { useEffect } from "react";
import { useRouterState } from "@tanstack/react-router";
import { setWorkspaceVisibility } from "@/actions/web-workspace";

export function WebWorkspaceRouteSync() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    const visible = pathname.startsWith("/web-workspace");
    setWorkspaceVisibility(visible).catch(() => undefined);
  }, [pathname]);

  return null;
}
