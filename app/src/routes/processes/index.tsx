import { createFileRoute } from "@tanstack/react-router";
import { ProcessesListPage } from "@/features/processes/processes-list";

export const Route = createFileRoute("/processes/")({
  component: ProcessesListPage,
});
