import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/processes/$instanceId")({
  component: ProcessInstanceLayout,
});

function ProcessInstanceLayout() {
  return <Outlet />;
}
