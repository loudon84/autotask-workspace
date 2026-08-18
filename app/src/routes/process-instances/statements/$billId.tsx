import { createFileRoute } from "@tanstack/react-router";
import { StatementDetailPage } from "@/features/statements/statement-detail";

export const Route = createFileRoute("/process-instances/statements/$billId")({
  component: StatementDetailRoute,
});

function StatementDetailRoute() {
  const { billId } = Route.useParams();
  return <StatementDetailPage billId={billId} />;
}
