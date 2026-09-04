import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useBoePackingList } from "@/features/boe-packing/api/use-boe-packing";
import {
  BOE_PACK_STAGE_TABS,
  boePackStageName,
  canRetryBoePack,
} from "@/features/boe-packing/boe-packing-model";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { BoePackListItem } from "@/types/boe-packing";
import { formatBeijingDateTime } from "@/utils/date-time";

export function BoePackingListPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("all");
  const [acting, setActing] = useState(false);
  const stage = tab === "all" ? undefined : tab;
  const { data, isLoading, refetch } = useBoePackingList({ stage });

  const columns = useMemo<ColumnDef<BoePackListItem>[]>(
    () => [
      { accessorKey: "invoiceNo", header: "供应商发票号" },
      { accessorKey: "customerName", header: "客户" },
      { accessorKey: "factory", header: "BOE 工厂" },
      {
        id: "stage",
        header: "阶段",
        cell: ({ row }) => (
          <Badge variant="outline">{boePackStageName(row.original.stage)}</Badge>
        ),
      },
      {
        id: "qty",
        header: "数量",
        cell: ({ row }) =>
          row.original.qtyMismatch ? (
            <Badge variant="destructive">不一致</Badge>
          ) : (
            "—"
          ),
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
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Button asChild size="sm" variant="outline">
              <Link
                params={{ instanceId: row.original.id }}
                to="/process-instances/invoice-packing/$instanceId"
              >
                详情
              </Link>
            </Button>
            {canRetryBoePack(row.original.stage) ? (
              <Button asChild size="sm">
                <Link
                  params={{ instanceId: row.original.id }}
                  to="/process-instances/invoice-packing/$instanceId"
                >
                  重试
                </Link>
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    []
  );

  return (
    <div className="space-y-6">
      <PageHeader
        actions={
          <div className="flex gap-2">
            <Button
              disabled={acting}
              onClick={async () => {
                setActing(true);
                try {
                  const result = await autotaskApi.boePacking.match();
                  if (result.error) {
                    toast.error(result.error);
                  } else {
                    toast.success(
                      `匹配完成：新建 ${result.createdCount}，跳过 ${result.skippedCount}`
                    );
                    if (result.missingPortal.length > 0) {
                      toast.warning(
                        `未找到门户：${result.missingPortal.join("、")}`
                      );
                    }
                  }
                  await queryClient.invalidateQueries({
                    queryKey: queryKeys.boePacking.all,
                  });
                  await refetch();
                } catch (error) {
                  toast.error(
                    error instanceof Error ? error.message : "匹配失败"
                  );
                } finally {
                  setActing(false);
                }
              }}
            >
              立即匹配交货计划
            </Button>
          </div>
        }
        description="按交货计划建单并读取 WMS 装箱信息。门户客户编号须等于子代码。"
        title="发票箱单"
      />
      <Tabs onValueChange={setTab} value={tab}>
        <TabsList>
          {BOE_PACK_STAGE_TABS.map((item) => (
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
