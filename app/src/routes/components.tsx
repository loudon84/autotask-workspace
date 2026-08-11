import { createFileRoute } from "@tanstack/react-router";
import { ComponentsPage } from "@/features/components";

export const Route = createFileRoute("/components")({
  component: ComponentsPage,
});
