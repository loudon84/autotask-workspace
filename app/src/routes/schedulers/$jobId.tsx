import { createFileRoute } from "@tanstack/react-router";
import { SchedulerJobDetailPage } from "@/features/schedulers/scheduler-job-detail";

export const Route = createFileRoute("/schedulers/$jobId")({
  component: SchedulerJobDetailRoute,
});

function SchedulerJobDetailRoute() {
  const { jobId } = Route.useParams();
  return <SchedulerJobDetailPage jobId={jobId} />;
}
