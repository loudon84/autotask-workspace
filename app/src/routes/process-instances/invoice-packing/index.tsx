import { createFileRoute } from "@tanstack/react-router";
import { BoePackingListPage } from "@/features/boe-packing/boe-packing-list";

export const Route = createFileRoute("/process-instances/invoice-packing/")({
  component: BoePackingListPage,
});
