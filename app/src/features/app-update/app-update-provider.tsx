import { useEffect, useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { useAppUpdate } from "./use-app-update";

/**
 * 在线更新弹窗：有新版 → 点立即更新则下载并安装；也可稍后，下完再点现在安装。
 */
export function AppUpdateProvider() {
  const { state, downloadAndInstall, install } = useAppUpdate();
  const [dismissedVersion, setDismissedVersion] = useState<string | null>(null);
  const [hideProgress, setHideProgress] = useState(false);

  useEffect(() => {
    if (state.status === "downloading" || state.status === "downloaded") {
      setDismissedVersion(null);
      if (state.status === "downloading") {
        setHideProgress(false);
      }
    }
  }, [state.status]);

  const dismissed = state.version != null && state.version === dismissedVersion;

  return (
    <>
      <AlertDialog open={state.status === "available" && !dismissed}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>发现新版本 {state.version}</AlertDialogTitle>
            <AlertDialogDescription>是否立即更新？</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button
              variant="outline"
              onClick={() => setDismissedVersion(state.version ?? null)}
            >
              稍后
            </Button>
            <Button
              onClick={(event) => {
                event.preventDefault();
                void downloadAndInstall();
              }}
            >
              立即更新
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setHideProgress(true);
          }
        }}
        open={state.status === "downloading" && !hideProgress}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>正在下载 {state.version}</DialogTitle>
            <DialogDescription>请稍候。</DialogDescription>
          </DialogHeader>
          <Progress value={state.percent ?? 0} />
          <p className="text-muted-foreground text-right text-sm">
            {state.percent ?? 0}%
          </p>
          <div className="flex justify-end">
            <Button onClick={() => setHideProgress(true)} variant="outline">
              后台下载
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={state.status === "downloaded" && !dismissed}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>新版本 {state.version} 已就绪</AlertDialogTitle>
            <AlertDialogDescription>安装时将关闭 AutoTask。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button
              variant="outline"
              onClick={() => setDismissedVersion(state.version ?? null)}
            >
              稍后
            </Button>
            <Button
              onClick={(event) => {
                event.preventDefault();
                void install();
              }}
            >
              现在安装
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={state.status === "error"}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>更新失败</AlertDialogTitle>
            <AlertDialogDescription>
              {state.message ?? "检查或安装更新时出错。"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction>确定</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
