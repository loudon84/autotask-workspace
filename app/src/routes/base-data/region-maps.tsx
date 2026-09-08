import { createFileRoute } from "@tanstack/react-router";
import { RegionMapsPage } from "@/features/base-data/region-maps-page";

export const Route = createFileRoute("/base-data/region-maps")({
  component: RegionMapsPage,
});
