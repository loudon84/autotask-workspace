import { createFileRoute } from "@tanstack/react-router";
import { PortalCategoriesListPage } from "@/features/portal-categories/portal-categories-list";

export const Route = createFileRoute("/portal-categories/")({
  component: PortalCategoriesListPage,
});
