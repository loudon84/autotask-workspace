import { createFileRoute } from "@tanstack/react-router";
import { WebWorkspacePage } from "@/features/web-workspace/web-workspace-page";

export const Route = createFileRoute("/web-workspace/")({
  component: WebWorkspacePage,
});
