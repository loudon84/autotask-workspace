import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/common/page-header";

export const Route = createFileRoute("/process-instances/statements")({
  component: StatementsProcessPlaceholderPage,
});

function StatementsProcessPlaceholderPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        description="按客户对账场景独立建模，字段与客户订单流程不同"
        title="对账单流程实例"
      />
      <p className="text-muted-foreground text-sm">
        即将推出。当前仅预留入口；客户订单请使用「客户订单流程实例」。
      </p>
    </div>
  );
}
