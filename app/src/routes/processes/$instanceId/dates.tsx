import { createFileRoute } from "@tanstack/react-router";
import { ProcessDatesPage } from "@/features/processes/process-dates";

export const Route = createFileRoute("/processes/$instanceId/dates")({
  component: ProcessDatesRoute,
});

function ProcessDatesRoute() {
  const { instanceId } = Route.useParams();
  return <ProcessDatesPage instanceId={instanceId} />;
}
