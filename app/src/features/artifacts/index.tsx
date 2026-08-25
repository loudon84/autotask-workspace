import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { Eye } from "lucide-react";
import { useState } from "react";
import {
  ArtifactDownloadButton,
  ArtifactPreviewDialog,
  isDownloadableArtifact,
} from "@/components/business/artifact-preview";
import { DataTable } from "@/components/common/data-table";
import { FilterBar } from "@/components/common/filter-bar";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { SearchInput } from "@/components/common/search-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useArtifacts } from "@/features/artifacts/api/use-artifacts";
import type { Artifact, ArtifactType } from "@/types/artifact";
import { formatBeijingDateTime } from "@/utils/date-time";

const typeLabels: Record<ArtifactType, string> = {
  screenshot: "截图",
  download: "下载文件",
  upload: "上传文件",
  trace: "Trace",
  dom_snapshot: "DOM 快照",
  log: "日志",
};

export function ArtifactsPage() {
  const [keyword, setKeyword] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [preview, setPreview] = useState<Artifact | null>(null);

  const { data: artifacts = [], isLoading } = useArtifacts();

  const filtered = artifacts.filter((a) => {
    if (typeFilter !== "all" && a.type !== typeFilter) {
      return false;
    }
    if (keyword && !a.name.toLowerCase().includes(keyword.toLowerCase())) {
      return false;
    }
    return true;
  });

  const columns: ColumnDef<Artifact>[] = [
    { accessorKey: "name", header: "文件名" },
    {
      accessorKey: "type",
      header: "类型",
      cell: ({ row }) => (
        <Badge variant="outline">{typeLabels[row.original.type]}</Badge>
      ),
    },
    { accessorKey: "customerName", header: "客户" },
    { accessorKey: "taskTitle", header: "任务" },
    { accessorKey: "runId", header: "Run ID" },
    { accessorKey: "sizeText", header: "大小" },
    {
      accessorKey: "createdAt",
      header: "创建时间（北京时间）",
      cell: ({ row }) => formatBeijingDateTime(row.original.createdAt),
    },
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button
            aria-label={`预览 ${row.original.name}`}
            onClick={() => setPreview(row.original)}
            size="sm"
            title={`预览 ${row.original.name}`}
            variant="ghost"
          >
            <Eye className="h-4 w-4" />
          </Button>
          {isDownloadableArtifact(row.original) ? (
            <ArtifactDownloadButton artifact={row.original} iconOnly />
          ) : null}
          <Button asChild size="sm" variant="ghost">
            <Link params={{ taskId: row.original.taskId }} to="/tasks/$taskId">
              任务
            </Link>
          </Button>
          <Button asChild size="sm" variant="ghost">
            <Link params={{ runId: row.original.runId }} to="/runs/$runId">
              运行
            </Link>
          </Button>
        </div>
      ),
    },
  ];

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader
        description="RPA 执行产生的截图、文件与日志"
        title="证据中心"
      />

      <FilterBar>
        <SearchInput
          className="w-48"
          onChange={setKeyword}
          placeholder="关键词..."
          value={keyword}
        />
        <Select onValueChange={setTypeFilter} value={typeFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="文件类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部类型</SelectItem>
            {Object.entries(typeLabels).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FilterBar>

      <DataTable columns={columns} data={filtered} />

      <ArtifactPreviewDialog
        artifact={preview}
        onOpenChange={(open) => {
          if (!open) {
            setPreview(null);
          }
        }}
      />
    </div>
  );
}
