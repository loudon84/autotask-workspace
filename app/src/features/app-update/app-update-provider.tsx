import { useEffect, useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
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
 * 在线更新弹窗：有新版 → 用户点下载 → 进度 → 下完点安装。
 * 「稍后」只关掉本次弹窗，下次状态变化（如下载完成）还会再弹。
 */
export function AppUpdateProvider() {
  const { state, download, install } = useAppUpdate();
  const [dismissedVersion, setDismissedVersion] = useState<string | null>(null);
  const [hideProgress, setHideProgress] = useState(false);

  // 新版本出现时重置「稍后」记忆
  useEffect(() => {
    if (state.status === "available" && state.version !== dismissedVersion) {
      setDismissedVersion(null);
    }
  }, [state.status, state.version, dismissedVersion]);

  const dismissed = state.version != null && state.version === dismissedVersion;

  return (
    <>
      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setDismissedVersion(state.version ?? null);
          }
        }}
        open={state.status === "available" && !dismissed}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>发现新版本 {state.version}</AlertDialogTitle>
            <AlertDialogDescription>
              下载后随时可以安装，不影响现在使用。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>稍后</AlertDialogCancel>
            <AlertDialogAction onClick={() => void download()}>
              下载更新
            </AlertDialogAction>
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
            <DialogDescription>下载完成后会提示安装。</DialogDescription>
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

      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setDismissedVersion(state.version ?? null);
          }
        }}
        open={state.status === "downloaded" && !dismissed}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>新版本 {state.version} 已就绪</AlertDialogTitle>
            <AlertDialogDescription>
              安装会自动重启 AutoTask，未保存的工作请先处理。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>稍后</AlertDialogCancel>
            <AlertDialogAction onClick={install}>现在安装</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
