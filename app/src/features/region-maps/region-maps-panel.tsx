import { Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DataTable } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useDeleteRegionMap,
  useRegionMaps,
  useUpsertRegionMap,
} from "@/features/region-maps/api/use-region-maps";
import type { RegionCodeMap } from "@/types/region-map";
import type { ColumnDef } from "@tanstack/react-table";

export function RegionMapsPanel({ category }: { category: string }) {
  const { data: rows = [], isLoading } = useRegionMaps(category);
  const upsertMutation = useUpsertRegionMap(category);
  const deleteMutation = useDeleteRegionMap(category);
  const [regionCode, setRegionCode] = useState("");
  const [srmDisplayName, setSrmDisplayName] = useState("");

  const columns: ColumnDef<RegionCodeMap>[] = useMemo(
    () => [
      { accessorKey: "regionCode", header: "WMS 地区编号" },
      { accessorKey: "srmDisplayName", header: "SRM 显示名" },
      {
        accessorKey: "updatedByName",
        header: "维护人",
        cell: ({ row }) => row.original.updatedByName || "—",
      },
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => (
          <Button
            disabled={deleteMutation.isPending}
            onClick={() => {
              deleteMutation.mutate(row.original.id, {
                onSuccess: () => toast.success("已删除"),
                onError: (error) =>
                  toast.error(error instanceof Error ? error.message : "删除失败"),
              });
            }}
            size="sm"
            variant="ghost"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        ),
      },
    ],
    [deleteMutation]
  );

  const onSave = async () => {
    try {
      await upsertMutation.mutateAsync({
        regionCode: regionCode.trim(),
        srmDisplayName: srmDisplayName.trim(),
      });
      setRegionCode("");
      setSrmDisplayName("");
      toast.success("已保存地区对照");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>地区对照</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground text-sm">
          WMS 地区编号映射到京东方 SRM 下拉显示名。缺映射时发票箱单行标红，不拦读
          WMS；核验时手工补选。表未迁库前保存会提示授权执行迁移。
        </p>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="space-y-1">
            <Label htmlFor="regionCode">WMS 地区编号</Label>
            <Input
              id="regionCode"
              onChange={(event) => setRegionCode(event.target.value)}
              placeholder="TAIWAN,CHINA"
              value={regionCode}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="srmDisplayName">SRM 显示名</Label>
            <Input
              id="srmDisplayName"
              onChange={(event) => setSrmDisplayName(event.target.value)}
              placeholder="台湾"
              value={srmDisplayName}
            />
          </div>
          <div className="flex items-end">
            <Button
              disabled={
                upsertMutation.isPending ||
                !regionCode.trim() ||
                !srmDisplayName.trim()
              }
              onClick={() => void onSave()}
            >
              保存对照
            </Button>
          </div>
        </div>
        {isLoading ? null : rows.length === 0 ? (
          <EmptyState
            description="先维护编号与 SRM 名称，再匹配交货计划"
            title="还没有地区对照"
          />
        ) : (
          <DataTable columns={columns} data={rows} />
        )}
      </CardContent>
    </Card>
  );
}
