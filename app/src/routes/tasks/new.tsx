import { createFileRoute } from "@tanstack/react-router";
import { TaskNewPage } from "@/features/tasks/task-new";

export const Route = createFileRoute("/tasks/new")({
  component: TaskNewPage,
});
