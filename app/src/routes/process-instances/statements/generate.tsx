import { createFileRoute } from "@tanstack/react-router";
import { StatementGeneratePage } from "@/features/statements/statement-generate";

export const Route = createFileRoute("/process-instances/statements/generate")({
  component: StatementGeneratePage,
});
