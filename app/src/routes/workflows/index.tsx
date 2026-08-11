import { createFileRoute } from "@tanstack/react-router";
import { WorkflowsListPage } from "@/features/workflows/workflows-list";

export const Route = createFileRoute("/workflows/")({
  component: WorkflowsListPage,
});
