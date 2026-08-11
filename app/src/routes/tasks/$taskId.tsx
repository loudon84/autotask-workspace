import { createFileRoute } from "@tanstack/react-router";
import { TaskDetailPage } from "@/features/tasks/task-detail";

export const Route = createFileRoute("/tasks/$taskId")({
  component: TaskDetailRoute,
});

function TaskDetailRoute() {
  const { taskId } = Route.useParams();
  return <TaskDetailPage taskId={taskId} />;
}
