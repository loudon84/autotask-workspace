import { createFileRoute } from "@tanstack/react-router";
import { SchedulersListPage } from "@/features/schedulers/schedulers-list";

export const Route = createFileRoute("/schedulers/")({
  component: SchedulersListPage,
});
