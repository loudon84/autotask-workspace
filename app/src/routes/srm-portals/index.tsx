import { createFileRoute } from "@tanstack/react-router";
import { SrmPortalsListPage } from "@/features/srm-portals/srm-portals-list";

export const Route = createFileRoute("/srm-portals/")({
  component: SrmPortalsListPage,
});
