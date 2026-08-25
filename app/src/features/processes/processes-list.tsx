import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { RefreshCw, ScanSearch, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { FilterBar } from "@/components/common/filter-bar";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { SearchInput } from "@/components/common/search-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useProcessInstances } from "@/features/processes/api/use-process-instances";
import {
  CUSTOMER_ORDER_PROCESS_CODE,
  formatProcessError,
  stageActionPath,
  stageButton,
  stageName,
  statusLabel,
} from "@/features/processes/process-model";
import {
  resolvePortalCustomerName,
  usePortalNameMap,
} from "@/features/processes/use-portal-name-map";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { ProcessInstanceListItem } from "@/types/process-instance";
import { formatBeijingDateTime } from "@/utils/date-time";

const stageTabs: { value: string; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "CREATING_SDMS", label: "建单中" },
  { value: "SDMS_CREATED", label: "待填写交期" },
  { value: "DATES_PARTIAL", label: "交期填写中" },
  { value: "DATES_COMPLETE", label: "待签章" },
  { value: "SIGN_REQUESTED", label: "待回签" },
  { value: "SIGNED", label: "已回签" },
  { value: "ARCHIVED", label: "已完成" },
  { value: "FAILED", label: "失败" },
];

function statusVariant(
  status: ProcessInstanceListItem["status"]
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "COMPLETED":
      return "default";
    case "FAILED":
      return "destructive";
    case "CANCELLED":
      return "outline";
    default:
      return "secondary";
  }
}

export function ProcessesListPage() {
  const queryClient = useQueryClient();
  const [stageTab, setStageTab] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [scanning, setScanning] = useState(false);
  const [polling, setPolling] = useState(false);
  const portalNameMap = usePortalNameMap();

  const { data: instances = [], isLoading } = useProcessInstances(
    stageTab === "all" ? undefined : { stage: stageTab }
  );

  const onUpdate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.processInstances.all });
  };

  const triggerScan = async () => {
    setScanning(true);
    try {
      const portals = await autotaskApi.portalAccounts.list();
      const enabled = portals.filter((portal) => portal.status === "ENABLED");
      if (enabled.length === 0) {
        toast.error("没有已启用的客户门户");
        return;
      }
      let ok = 0;
      const failed: string[] = [];
      for (const portal of enabled) {
        try {
          await autotaskApi.processInstances.triggerScan(portal.id);
          ok += 1;
        } catch (error) {
          failed.push(
            `${portal.portalName}: ${error instanceof Error ? error.message : "失败"}`
          );
        }
      }
      if (ok > 0) {
        toast.success(`已触发 ${ok} 个门户的扫单任务`);
      }
      if (failed.length > 0) {
        toast.error(`以下门户扫单失败：\n${failed.join("\n")}`);
      }
      onUpdate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "触发扫单失败");
    } finally {
      setScanning(false);
    }
  };

  const triggerSignPoll = async () => {
    setPolling(true);
    try {
      const result = await autotaskApi.processInstances.runSignPollOnce();
      toast.success(
        `回签轮询已触发：候选 ${result.candidateCount}，新建探测 ${result.createdCount}`
      );
      onUpdate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "立即回签轮询失败");
    } finally {
      setPolling(false);
    }
  };

  const filtered = instances.filter((item) => {
    if (item.processCode !== CUSTOMER_ORDER_PROCESS_CODE) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    const lower = keyword.toLowerCase();
    const customer = resolvePortalCustomerName(
      portalNameMap,
      item.portalAccountId,
      ""
    ).toLowerCase();
    return (
      item.bizKey.toLowerCase().includes(lower) ||
      item.title.toLowerCase().includes(lower) ||
      customer.includes(lower)
    );
  });

  const columns: ColumnDef<ProcessInstanceListItem>[] = useMemo(
    () => [
      {
        accessorKey: "bizKey",
        header: "客户订单",
        meta: { sticky: "left" },
        cell: ({ row }) => (
          <Link
            className="font-medium hover:underline"
            params={{ instanceId: row.original.id }}
            to="/processes/$instanceId"
          >
            {row.original.bizKey}
          </Link>
        ),
      },
      {
        id: "customer",
        header: "客户",
        cell: ({ row }) =>
          resolvePortalCustomerName(
            portalNameMap,
            row.original.portalAccountId
          ),
      },
      { accessorKey: "title", header: "流程" },
      {
        accessorKey: "stage",
        header: "阶段",
        cell: ({ row }) => (
          <Badge variant="outline">{stageName(row.original.stage)}</Badge>
        ),
      },
      {
        id: "progress",
        header: "进度",
        cell: ({ row }) =>
          row.original.lineTotal > 0
            ? `${row.original.lineDone}/${row.original.lineTotal}`
            : "—",
      },
      {
        accessorKey: "status",
        header: "运行状态",
        cell: ({ row }) => (
          <Badge variant={statusVariant(row.original.status)}>
            {statusLabel(row.original.status)}
          </Badge>
        ),
      },
      {
        accessorKey: "lastErrorMessage",
        header: "最近错误",
        cell: ({ row }) => {
          const { status, lastErrorCode, lastErrorMessage } = row.original;
          // 已完成/已取消不再展示历史错误，避免误导
          if (status === "COMPLETED" || status === "CANCELLED") {
            return "";
          }
          const text = formatProcessError(lastErrorCode, lastErrorMessage);
          return text ? (
            <span className="text-destructive text-sm">{text}</span>
          ) : (
            ""
          );
        },
      },
      {
        accessorKey: "updatedAt",
        header: "更新时间（北京时间）",
        cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
      },
      {
        id: "actions",
        header: "操作",
        meta: { sticky: "right" },
        cell: ({ row }) => {
          const button = stageButton(row.original.stage);
          if (!button) {
            return null;
          }
          return (
            <Button asChild size="sm" variant="outline">
              <Link
                params={{ instanceId: row.original.id }}
                to={stageActionPath(row.original.stage)}
              >
                {button}
              </Link>
            </Button>
          );
        },
      },
    ],
    [portalNameMap]
  );

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader
        description="按客户门户定制的客户订单 SOP（阶段与字段与对账单等流程不同）"
        title="天地伟业-客户订单流程实例"
      >
        <Button
          disabled={polling}
          onClick={triggerSignPoll}
          type="button"
          variant="outline"
        >
          {polling ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <TimerReset className="mr-2 h-4 w-4" />
          )}
          立即回签轮询
        </Button>
        <Button
          disabled={scanning}
          onClick={triggerScan}
          type="button"
          variant="outline"
        >
          {scanning ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <ScanSearch className="mr-2 h-4 w-4" />
          )}
          手动扫单
        </Button>
      </PageHeader>

      <FilterBar>
        <SearchInput
          className="w-56"
          onChange={setKeyword}
          placeholder="搜索客户订单号 / 客户..."
          value={keyword}
        />
      </FilterBar>

      <Tabs onValueChange={setStageTab} value={stageTab}>
        <TabsList>
          {stageTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <DataTable columns={columns} data={filtered} />
    </div>
  );
}
