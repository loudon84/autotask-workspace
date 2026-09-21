import { useEffect, useState } from "react";
import { getAppVersion } from "@/actions/app";
import { useAppUpdate } from "@/features/app-update/use-app-update";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** 当前版本与手动检查更新，交互对齐 SMC-Copilot 设置里的「关于与更新」。 */
// @lat: [[client#Online Updates#User-facing update UI]]
export function AboutPane() {
  const { state, check, downloadAndInstall, install } = useAppUpdate();
  const [version, setVersion] = useState("");

  useEffect(() => {
    void getAppVersion()
      .then((value) => {
        if (typeof value === "string") {
          setVersion(value);
        }
      })
      .catch(() => {
        setVersion("");
      });
  }, []);

  const supported = state.supported === true;
  const busy =
    state.status === "checking" ||
    state.status === "downloading" ||
    state.status === "downloaded";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">关于与更新</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <p className="text-muted-foreground text-sm">当前版本</p>
          <p className="font-medium text-sm">{version || "…"}</p>
        </div>
        {state.status === "uptodate" ? (
          <p className="text-muted-foreground text-sm">已是最新版本</p>
        ) : null}
        {state.status === "available" && state.version ? (
          <p className="text-sm">发现新版本 {state.version}</p>
        ) : null}
        {!supported ? (
          <p className="text-muted-foreground text-sm">仅安装版可检查更新。</p>
        ) : null}
        <DesktopUpdateButton
          busy={busy}
          onAct={() => {
            if (state.status === "downloaded") {
              void install();
              return;
            }
            void downloadAndInstall();
          }}
          onCheck={() => {
            void check();
          }}
          percent={state.percent ?? 0}
          status={state.status}
          supported={supported}
          version={state.version}
        />
      </CardContent>
    </Card>
  );
}

function DesktopUpdateButton({
  busy,
  onAct,
  onCheck,
  percent,
  status,
  supported,
  version,
}: {
  busy: boolean;
  onAct: () => void;
  onCheck: () => void;
  percent: number;
  status: string;
  supported: boolean;
  version?: string;
}) {
  if (status === "downloading") {
    return (
      <Button disabled>
        正在下载 {percent}%
      </Button>
    );
  }
  if (status === "downloaded") {
    return <Button onClick={onAct}>现在安装</Button>;
  }
  if (status === "available") {
    return (
      <Button disabled={busy} onClick={onAct}>
        {version ? `更新到 ${version}` : "立即更新"}
      </Button>
    );
  }
  if (status === "checking") {
    return <Button disabled>检查中...</Button>;
  }
  return (
    <Button disabled={!supported || busy} onClick={onCheck} variant="outline">
      {status === "error" ? "重试" : "检查更新"}
    </Button>
  );
}
