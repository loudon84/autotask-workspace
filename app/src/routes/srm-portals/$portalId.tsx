import { createFileRoute } from "@tanstack/react-router";
import { SrmPortalDetailPage } from "@/features/srm-portals/srm-portal-detail";

export const Route = createFileRoute("/srm-portals/$portalId")({
  component: SrmPortalDetailRoute,
});

function SrmPortalDetailRoute() {
  const { portalId } = Route.useParams();
  return <SrmPortalDetailPage portalId={portalId} />;
}
