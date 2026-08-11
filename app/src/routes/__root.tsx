import { createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { Activity } from "react";
import { inDevelopment } from "@/constants";
import { AppShell } from "@/components/layout/app-shell";
import BaseLayout from "@/layouts/base-layout";

function Root() {
  return (
    <BaseLayout>
      <AppShell />
      <Activity mode={inDevelopment ? "visible" : "hidden"}>
        <TanStackRouterDevtools />
      </Activity>
    </BaseLayout>
  );
}

export const Route = createRootRoute({
  component: Root,
});
