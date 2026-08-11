import { createFileRoute } from "@tanstack/react-router";
import { TasksListPage } from "@/features/tasks/tasks-list";

export const Route = createFileRoute("/tasks/")({
  component: TasksListPage,
});
