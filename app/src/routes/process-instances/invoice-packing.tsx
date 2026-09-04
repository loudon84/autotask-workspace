import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/process-instances/invoice-packing")({
  component: BoePackingLayout,
});

function BoePackingLayout() {
  return <Outlet />;
}
