import { createFileRoute } from "@tanstack/react-router";
import { ProcessDetailPage } from "@/features/processes/process-detail";

export const Route = createFileRoute("/processes/$instanceId/")({
  component: ProcessDetailRoute,
});

function ProcessDetailRoute() {
  const { instanceId } = Route.useParams();
  return <ProcessDetailPage instanceId={instanceId} />;
}
