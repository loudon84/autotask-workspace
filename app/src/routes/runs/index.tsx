import { createFileRoute } from "@tanstack/react-router";
import { RunsListPage } from "@/features/runs/runs-list";

export const Route = createFileRoute("/runs/")({
  component: RunsListPage,
});
