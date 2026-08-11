import { createFileRoute } from "@tanstack/react-router";
import { WorkflowDetailPage } from "@/features/workflows/workflow-detail";

export const Route = createFileRoute("/workflows/$workflowId")({
  component: WorkflowDetailRoute,
});

function WorkflowDetailRoute() {
  const { workflowId } = Route.useParams();
  return <WorkflowDetailPage workflowId={workflowId} />;
}
