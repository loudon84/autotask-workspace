import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/process-instances/statements")({
  component: StatementsLayout,
});

function StatementsLayout() {
  return <Outlet />;
}
