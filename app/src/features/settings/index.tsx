import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { setTheme } from "@/actions/theme";
import { clearAllWebSessions } from "@/actions/web-workspace";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useSettings,
  useUpdateSettings,
} from "@/features/settings/api/use-settings";
import type { AppSettings } from "@/types/settings";
import type { ThemeMode } from "@/types/theme-mode";

export function SettingsPage() {
  const [tab, setTab] = useState("basic");

  const {
    data: settings,
    error,
    isError,
    isFetching,
    isLoading,
    refetch,
  } = useSettings();
  const updateMutation = useUpdateSettings();

  if (isLoading) {
    return <MockLoading />;
  }

  if (isError || !settings) {
    return (
      <div className="space-y-4">
        <PageHeader
          description="本地 Task 尚未提供系统设置接口"
          title="系统设置"
        />
        <Card>
          <CardHeader>
            <CardTitle className="text-base">系统设置暂不可用</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-muted-foreground text-sm">
              当前服务没有提供 GET
              /api/v1/autotask/settings，无法读取或保存服务器设置。 请等待 Task
              接口接入后重新检查。
            </p>
            {error instanceof Error && (
              <p className="text-destructive text-xs">{error.message}</p>
            )}
            <Button
              disabled={isFetching}
              onClick={() => {
                refetch();
              }}
              variant="outline"
            >
              {isFetching ? "检查中..." : "重新检查"}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const update = (patch: Partial<AppSettings>) => {
    updateMutation.mutate(patch, {
      onSuccess: () => toast.success("设置已保存"),
    });
  };

  const handleThemeChange = async (theme: ThemeMode) => {
    await setTheme(theme);
    update({ themeMode: theme });
  };

  const handleClearAllCache = async () => {
    try {
      await clearAllWebSessions();
      toast.success("已清理所有 Web 工作区缓存");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "清理失败");
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader description="本地原型配置" title="系统设置" />

      <Tabs onValueChange={setTab} value={tab}>
        <TabsList>
          <TabsTrigger value="basic">基础设置</TabsTrigger>
          <TabsTrigger value="web-workspace">Web 工作区</TabsTrigger>
          <TabsTrigger value="worker">Worker 设置</TabsTrigger>
          <TabsTrigger value="storage">存储设置</TabsTrigger>
          <TabsTrigger value="appearance">外观设置</TabsTrigger>
          <TabsTrigger value="mock">Mock 数据设置</TabsTrigger>
        </TabsList>

        <TabsContent value="basic">
          <SettingsCard title="基础设置">
            <Field label="日志级别">
              <Select
                onValueChange={(v) =>
                  update({ logLevel: v as AppSettings["logLevel"] })
                }
                value={settings.logLevel}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["DEBUG", "INFO", "WARN", "ERROR"].map((l) => (
                    <SelectItem key={l} value={l}>
                      {l}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </SettingsCard>
        </TabsContent>

        <TabsContent value="web-workspace">
          <SettingsCard title="Web 工作区设置">
            <Field label="默认打开方式">
              <Select
                onValueChange={(v) =>
                  update({
                    defaultOpenMode: v as AppSettings["defaultOpenMode"],
                  })
                }
                value={settings.defaultOpenMode}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="webcontents">内置 Web 工作区</SelectItem>
                  <SelectItem value="system_browser">
                    系统浏览器（兜底）
                  </SelectItem>
                </SelectContent>
              </Select>
            </Field>

            <Field label="下载目录">
              <Input
                onChange={(e) => update({ downloadsRootPath: e.target.value })}
                value={settings.downloadsRootPath}
              />
            </Field>

            <SwitchField
              checked={settings.allowResetSession}
              label="允许清理 Portal 登录态"
              onCheckedChange={(v) => update({ allowResetSession: v })}
            />
            <SwitchField
              checked={settings.allowClearAllCache}
              label="允许清理所有 Web 缓存"
              onCheckedChange={(v) => update({ allowClearAllCache: v })}
            />

            {settings.allowClearAllCache && (
              <Button onClick={handleClearAllCache} variant="outline">
                <Trash2 className="mr-2 h-4 w-4" /> 清理所有 Web 工作区缓存
              </Button>
            )}

            <p className="text-muted-foreground text-xs">
              Web 工作区使用 Electron session partition 隔离各客户 SRM
              登录态，不与服务器 RPA 共享。
            </p>
          </SettingsCard>
        </TabsContent>

        <TabsContent value="worker">
          <SettingsCard title="Worker 设置">
            <SwitchField
              checked={true}
              label="失败自动重试"
              onCheckedChange={() => toast.info("Mock 设置，未持久化")}
            />
          </SettingsCard>
        </TabsContent>

        <TabsContent value="storage">
          <SettingsCard title="存储设置">
            <Field label="Artifact 本地路径">
              <Input
                onChange={(e) => update({ artifactPath: e.target.value })}
                value={settings.artifactPath}
              />
            </Field>
            <SwitchField
              checked={settings.saveScreenshots}
              label="保存截图"
              onCheckedChange={(v) => update({ saveScreenshots: v })}
            />
            <SwitchField
              checked={settings.enableTrace}
              label="开启 Trace"
              onCheckedChange={(v) => update({ enableTrace: v })}
            />
          </SettingsCard>
        </TabsContent>

        <TabsContent value="appearance">
          <SettingsCard title="外观设置">
            <Field label="主题模式">
              <Select
                onValueChange={(v) => handleThemeChange(v as ThemeMode)}
                value={settings.themeMode}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">浅色</SelectItem>
                  <SelectItem value="dark">深色</SelectItem>
                  <SelectItem value="system">跟随系统</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </SettingsCard>
        </TabsContent>

        <TabsContent value="mock">
          <SettingsCard title="Mock 数据设置">
            <Field label="Mock 延迟时间 (ms)">
              <Input
                onChange={(e) =>
                  update({ mockDelayMs: Number(e.target.value) })
                }
                type="number"
                value={settings.mockDelayMs}
              />
            </Field>
            <p className="text-muted-foreground text-xs">
              模拟 API 请求延迟，用于测试 loading 状态。
            </p>
          </SettingsCard>
        </TabsContent>
      </Tabs>
    </div>
  );
}


function SettingsCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function Field({
  htmlFor,
  label,
  children,
}: {
  htmlFor?: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

function SwitchField({
  id,
  label,
  checked,
  onCheckedChange,
}: {
  id?: string;
  label: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <Label htmlFor={id}>{label}</Label>
      <Switch checked={checked} id={id} onCheckedChange={onCheckedChange} />
    </div>
  );
}
