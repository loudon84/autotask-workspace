import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { FilePlus2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  resolvePortalCustomerName,
  usePortalNameMap,
} from "@/features/processes/use-portal-name-map";
import { useStatements } from "@/features/statements/api/use-statements";
import {
  STATEMENT_STAGE_BUTTON,
  STATEMENT_STAGE_TABS,
  formatAmount,
  resolvePersistedStage,
  statementStageName,
  statementStatusLabel,
} from "@/features/statements/statement-model";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { StatementBillListItem } from "@/types/statement";
import { formatBeijingDateTime } from "@/utils/date-time";

export function StatementsListPage() {
  const queryClient = useQueryClient();
  const portalNameMap = usePortalNameMap();
  const [tab, setTab] = useState("all");
  const [actingId, setActingId] = useState<string | null>(null);
  const stage = tab === "all" ? undefined : tab;
  const { data, isLoading, isFetching, refetch } = useStatements({
    stage,
  });

  const columns = useMemo<ColumnDef<StatementBillListItem>[]>(
    () => [
      {
        id: "customer",
        header: "客户",
        cell: ({ row }) =>
          resolvePortalCustomerName(
            portalNameMap,
            row.original.portalAccountId
          ),
      },
      {
        accessorKey: "checkDate",
        header: "对账日期",
      },
      {
        accessorKey: "checkAmount",
        header: "对账金额",
        cell: ({ row }) => formatAmount(row.original.checkAmount),
      },
      {
        id: "stage",
        header: "阶段",
        cell: ({ row }) => (
          <Badge variant="outline">
            {statementStageName(resolvePersistedStage(row.original))}
          </Badge>
        ),
      },
      {
        id: "instanceStatus",
        header: "运行状态",
        cell: ({ row }) =>
          statementStatusLabel(row.original.instanceStatus),
      },
      {
        accessorKey: "updatedAt",
        header: "更新时间",
        cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
      },
      {
        id: "actions",
        header: "操作",
        meta: { sticky: "right" },
        cell: ({ row }) => {
          const bill = row.original;
          const persisted = resolvePersistedStage(bill);
          const stageButton = STATEMENT_STAGE_BUTTON[persisted];
          const canCancel =
            persisted === "STMT_GENERATING" ||
            persisted === "STMT_PENDING_INVOICE" ||
            persisted === "STMT_PENDING_REVIEW";
          return (
            <div className="flex items-center gap-2">
              <Button asChild size="sm" variant="outline">
                <Link
                  params={{ billId: bill.id }}
                  to="/process-instances/statements/$billId"
                >
                  详情
                </Link>
              </Button>
              {stageButton ? (
                <Button asChild size="sm">
                  <Link
                    params={{ billId: bill.id }}
                    to="/process-instances/statements/$billId"
                  >
                    {stageButton}
                  </Link>
                </Button>
              ) : null}
              {canCancel ? (
                <Button
                  disabled={actingId === bill.id}
                  onClick={async () => {
                    if (!window.confirm("确认取消对账？仅更新本地状态。")) {
                      return;
                    }
                    setActingId(bill.id);
                    try {
                      await autotaskApi.statements.cancel(bill.id);
                      toast.success("已作废");
                      await queryClient.invalidateQueries({
                        queryKey: queryKeys.statements.all,
                      });
                    } catch (error) {
                      toast.error(
                        error instanceof Error ? error.message : "取消失败"
                      );
                    } finally {
                      setActingId(null);
                    }
                  }}
                  size="sm"
                  variant="ghost"
                >
                  取消对账
                </Button>
              ) : null}
            </div>
          );
        },
      },
    ],
    [actingId, portalNameMap, queryClient]
  );

  return (
    <div className="space-y-4">
      <PageHeader
        description="天地伟业对账单 SOP：待创建与 SDMS 核准在填单页，落库后按阶段推进"
        title="天地伟业-对账单流程实例"
      >
        <div className="flex items-center gap-2">
          <Button
            disabled={isFetching}
            onClick={() => void refetch()}
            size="sm"
            variant="outline"
          >
            刷新
          </Button>
          <Button asChild size="sm">
            <Link to="/process-instances/statements/generate">
              <FilePlus2 className="mr-1 h-4 w-4" />
              生成客户对账单
            </Link>
          </Button>
        </div>
      </PageHeader>

      <Tabs onValueChange={setTab} value={tab}>
        <TabsList>
          {STATEMENT_STAGE_TABS.map((item) => (
            <TabsTrigger key={item.value} value={item.value}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <MockLoading />
      ) : (
        <DataTable columns={columns} data={data ?? []} />
      )}
    </div>
  );
}
