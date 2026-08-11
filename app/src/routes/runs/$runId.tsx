import { createFileRoute } from "@tanstack/react-router";
import { RunDetailPage } from "@/features/runs/run-detail";

export const Route = createFileRoute("/runs/$runId")({
  component: RunDetailRoute,
});

function RunDetailRoute() {
  const { runId } = Route.useParams();
  return <RunDetailPage runId={runId} />;
}
