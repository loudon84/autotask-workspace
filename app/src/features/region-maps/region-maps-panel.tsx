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

export function RegionMapsPanel() {
  const { data: rows = [], isLoading } = useRegionMaps();
  const upsertMutation = useUpsertRegionMap();
  const deleteMutation = useDeleteRegionMap();
  const [regionCode, setRegionCode] = useState("");
  const [defaultName, setDefaultName] = useState("");
  const [boeName, setBoeName] = useState("");

  const columns: ColumnDef<RegionCodeMap>[] = useMemo(
    () => [
      { accessorKey: "regionCode", header: "地区编号" },
      { accessorKey: "defaultName", header: "默认显示名" },
      {
        accessorKey: "boeName",
        header: "京东方显示名",
        cell: ({ row }) => row.original.boeName || "（同默认名）",
      },
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
        defaultName: defaultName.trim(),
        boeName: boeName.trim() || undefined,
      });
      setRegionCode("");
      setDefaultName("");
      setBoeName("");
      toast.success("已保存地区对照");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>地区编号对照</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground text-sm">
          地区编号全 SRM 共用一行：默认显示名必填；京东方显示名留空则用默认名，
          只有显示不同的才需要单独维护。缺映射时发票箱单行标红，不拦读
          WMS；核验时手工补选。
        </p>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="space-y-1">
            <Label htmlFor="regionCode">地区编号</Label>
            <Input
              id="regionCode"
              onChange={(event) => setRegionCode(event.target.value)}
              placeholder="TAIWAN,CHINA"
              value={regionCode}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="defaultName">默认显示名</Label>
            <Input
              id="defaultName"
              onChange={(event) => setDefaultName(event.target.value)}
              placeholder="中国台湾"
              value={defaultName}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="boeName">京东方显示名（可空）</Label>
            <Input
              id="boeName"
              onChange={(event) => setBoeName(event.target.value)}
              placeholder="留空则用默认名"
              value={boeName}
            />
          </div>
          <div className="flex items-end">
            <Button
              disabled={
                upsertMutation.isPending ||
                !regionCode.trim() ||
                !defaultName.trim()
              }
              onClick={() => void onSave()}
            >
              保存对照
            </Button>
          </div>
        </div>
        {isLoading ? null : rows.length === 0 ? (
          <EmptyState
            description="先维护编号与默认显示名，再匹配交货计划"
            title="还没有原产地对照"
          />
        ) : (
          <DataTable columns={columns} data={rows} />
        )}
      </CardContent>
    </Card>
  );
}
