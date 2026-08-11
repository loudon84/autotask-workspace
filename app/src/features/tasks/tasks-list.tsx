import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { useState } from "react";
import { PriorityBadge } from "@/components/business/priority-badge";
import { ProgressCell } from "@/components/business/progress-cell";
import { StatusBadge } from "@/components/business/status-badge";
import { TaskActions } from "@/components/business/task-actions";
import { DataTable } from "@/components/common/data-table";
import { FilterBar } from "@/components/common/filter-bar";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { SearchInput } from "@/components/common/search-input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTasks } from "@/features/tasks/api/use-tasks";
import { DELIVERY_DATE_TASK_TYPE } from "@/features/tasks/delivery-date-task-model";
import { queryKeys } from "@/services/query-keys";
import type { AutomationTask } from "@/types/automation-task";
import { formatBeijingDateTime } from "@/utils/date-time";

const statusTabs: { value: string; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "DRAFT", label: "待填写" },
  { value: "RUNNING", label: "运行中" },
  { value: "WAITING_HUMAN", label: "待人工" },
  { value: "HUMAN_OPERATING", label: "人工处理中" },
  { value: "FAILED", label: "失败" },
  { value: "SUCCESS", label: "成功" },
  { value: "SUCCESS_MANUAL", label: "人工完成" },
  { value: "READY", label: "待执行" },
];

export function TasksListPage() {
  const queryClient = useQueryClient();
  const [statusTab, setStatusTab] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [customer, setCustomer] = useState("all");

  const { data: tasks = [], isLoading } = useTasks();

  const onUpdate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    queryClient.invalidateQueries({ queryKey: ["human-action"] });
    queryClient.invalidateQueries({ queryKey: ["web-tabs"] });
  };

  const customers = [...new Set(tasks.map((t) => t.customerName))];

  const filtered = tasks.filter((t) => {
    if (statusTab !== "all" && t.status !== statusTab) {
      return false;
    }
    if (customer !== "all" && t.customerName !== customer) {
      return false;
    }
    if (keyword && !t.title.toLowerCase().includes(keyword.toLowerCase())) {
      return false;
    }
    return true;
  });

  const columns: ColumnDef<AutomationTask>[] = [
    {
      accessorKey: "title",
      header: "任务标题",
      cell: ({ row }) => (
        <Link
          className="font-medium hover:underline"
          params={{ taskId: row.original.id }}
          to="/tasks/$taskId"
        >
          {row.original.title}
        </Link>
      ),
    },
    { accessorKey: "customerName", header: "客户" },
    { accessorKey: "taskType", header: "任务类型" },
    { accessorKey: "workflowTemplateName", header: "流程模板" },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => (
        <StatusBadge
          labelOverride={
            row.original.status === "DRAFT" &&
            row.original.taskType === DELIVERY_DATE_TASK_TYPE
              ? "待填写"
              : undefined
          }
          status={row.original.status}
        />
      ),
    },
    {
      accessorKey: "priority",
      header: "优先级",
      cell: ({ row }) => <PriorityBadge priority={row.original.priority} />,
    },
    { accessorKey: "currentStep", header: "当前步骤" },
    {
      accessorKey: "progress",
      header: "进度",
      cell: ({ row }) => <ProgressCell progress={row.original.progress} />,
    },
    { accessorKey: "owner", header: "负责人" },
    {
      accessorKey: "createdAt",
      header: "创建时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.createdAt),
    },
    {
      accessorKey: "updatedAt",
      header: "更新时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.updatedAt),
    },
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => (
        <TaskActions
          compact
          onUpdate={onUpdate}
          status={row.original.status}
          taskId={row.original.id}
        />
      ),
    },
  ];

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader description="管理所有自动化任务" title="自动化任务">
        <Button asChild>
          <Link to="/tasks/new">
            <Plus className="mr-2 h-4 w-4" /> 新建任务
          </Link>
        </Button>
      </PageHeader>

      <FilterBar>
        <SearchInput
          className="w-48"
          onChange={setKeyword}
          placeholder="关键词搜索..."
          value={keyword}
        />
        <Select onValueChange={setCustomer} value={customer}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="客户" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部客户</SelectItem>
            {customers.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FilterBar>

      <Tabs onValueChange={setStatusTab} value={statusTab}>
        <TabsList>
          {statusTabs.map((tab) => (
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
