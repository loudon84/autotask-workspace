import { createFileRoute } from "@tanstack/react-router";
import { StatementsListPage } from "@/features/statements/statements-list";

export const Route = createFileRoute("/process-instances/statements/")({
  component: StatementsListPage,
});
