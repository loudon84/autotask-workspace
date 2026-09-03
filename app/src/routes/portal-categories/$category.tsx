import { createFileRoute } from "@tanstack/react-router";
import { PortalCategoryDocumentsPage } from "@/features/portal-categories/portal-category-documents";

export const Route = createFileRoute("/portal-categories/$category")({
  component: PortalCategoryDocumentsRoute,
});

function PortalCategoryDocumentsRoute() {
  const { category } = Route.useParams();
  return <PortalCategoryDocumentsPage category={category} />;
}
