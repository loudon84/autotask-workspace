import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { MockLoading } from "@/components/common/mock-loading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  useSchedulerSettings,
  useUpdateSchedulerSettings,
} from "@/features/settings/api/use-scheduler-settings";
import { CronParseError, cronNextAfter } from "@/features/settings/cron";

export function TenantSchedulerCard() {
  const { data, isLoading, isError } = useSchedulerSettings();
  const updateMutation = useUpdateSchedulerSettings();
  const [enabled, setEnabled] = useState(false);
  const [cron, setCron] = useState("0 7 * * *");

  useEffect(() => {
    if (!data) {
      return;
    }
    setEnabled(data.boePack.enabled);
    setCron(data.boePack.cron);
  }, [data?.boePack.enabled, data?.boePack.cron]);

  const previewText = useMemo(() => {
    try {
      const next = cronNextAfter(cron.trim() || "* * * * *", new Date());
      const formatted = next.toLocaleString("zh-CN", { hour12: false });
      return enabled ? formatted : `${formatted}（未启用）`;
    } catch (err) {
      return err instanceof CronParseError ? err.message : "表达式无效";
    }
  }, [cron, enabled]);

  const handleSave = () => {
    try {
      cronNextAfter(cron.trim(), new Date());
    } catch (err) {
      toast.error(err instanceof CronParseError ? err.message : "cron 无效");
      return;
    }
    updateMutation.mutate(
      { boePack: { enabled, cron: cron.trim() } },
      {
        onSuccess: () => toast.success("京东方匹配定时器已保存"),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "保存失败"),
      }
    );
  };

  if (isLoading) {
    return <MockLoading />;
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">京东方匹配交货计划</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-xs">
            无法加载租户级定时器。Binding 任务列表仍可使用。
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">京东方匹配交货计划</CardTitle>
        <p className="text-muted-foreground text-xs">
          租户级匹配交货计划，不按门户扫 SRM。开关与 cron 保存后约 30
          秒热生效，无需重启 Task。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <Label htmlFor="boe-pack-enabled">启用</Label>
          <Switch
            checked={enabled}
            id="boe-pack-enabled"
            onCheckedChange={setEnabled}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="boe-pack-cron">cron</Label>
          <Input
            id="boe-pack-cron"
            onChange={(e) => setCron(e.target.value)}
            value={cron}
          />
          <p className="text-muted-foreground text-xs">下次触发：{previewText}</p>
        </div>
        <Button disabled={updateMutation.isPending} onClick={handleSave}>
          {updateMutation.isPending ? "保存中..." : "保存"}
        </Button>
      </CardContent>
    </Card>
  );
}
