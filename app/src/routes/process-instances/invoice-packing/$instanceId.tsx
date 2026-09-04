import { createFileRoute } from "@tanstack/react-router";
import { BoePackingDetailPage } from "@/features/boe-packing/boe-packing-detail";

export const Route = createFileRoute(
  "/process-instances/invoice-packing/$instanceId"
)({
  component: BoePackingDetailRoute,
});

function BoePackingDetailRoute() {
  const { instanceId } = Route.useParams();
  return <BoePackingDetailPage instanceId={instanceId} />;
}
