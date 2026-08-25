import {
  AlertCircle,
  Code,
  Download as DownloadIcon,
  Eye,
  FileImage,
  FileText,
  LoaderCircle,
  RefreshCw,
  ScrollText,
  Upload,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { downloadFile } from "@/actions/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useArtifactDownloadUrl } from "@/features/artifacts/api/use-artifacts";
import type { Artifact, ArtifactType } from "@/types/artifact";

const typeIcons: Record<ArtifactType, React.ElementType> = {
  screenshot: FileImage,
  download: DownloadIcon,
  upload: Upload,
  trace: Code,
  dom_snapshot: Code,
  log: ScrollText,
};

const typeLabels: Record<ArtifactType, string> = {
  screenshot: "截图",
  download: "下载文件",
  upload: "上传文件",
  trace: "Trace",
  dom_snapshot: "DOM 快照",
  log: "日志",
};

export function isDownloadableArtifact(artifact: Artifact) {
  return artifact.type === "screenshot" || artifact.type === "download";
}

export function ArtifactDownloadButton({
  artifact,
  iconOnly = false,
}: {
  artifact: Artifact;
  iconOnly?: boolean;
}) {
  const download = useArtifactDownloadUrl(artifact.id, false);

  const handleDownload = async () => {
    try {
      const url = download.data ?? (await download.refetch()).data;
      if (!url) {
        throw new Error("未获取到下载地址");
      }
      await downloadFile(url);
      toast.success("已开始下载", { description: artifact.name });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文件下载失败");
    }
  };

  return (
    <Button
      aria-label={`下载 ${artifact.name}`}
      disabled={download.isFetching}
      onClick={handleDownload}
      size={iconOnly ? "icon-sm" : "sm"}
      title={`下载 ${artifact.name}`}
      type="button"
      variant={iconOnly ? "ghost" : "outline"}
    >
      {download.isFetching ? (
        <LoaderCircle className="animate-spin" />
      ) : (
        <DownloadIcon />
      )}
      {iconOnly ? <span className="sr-only">下载</span> : "下载"}
    </Button>
  );
}

export function ArtifactPreview({
  allowDownload = false,
  artifact,
  loadScreenshot = false,
  onPreview,
}: {
  allowDownload?: boolean;
  artifact: Artifact;
  loadScreenshot?: boolean;
  onPreview?: () => void;
}) {
  const Icon = typeIcons[artifact.type] ?? FileText;
  const isScreenshot = artifact.type === "screenshot";
  const canPreview = Boolean(onPreview) && isScreenshot && !loadScreenshot;
  const preview = useArtifactDownloadUrl(
    artifact.id,
    loadScreenshot && isScreenshot
  );
  const previewUnavailable =
    preview.isError || (preview.isSuccess && !preview.data);

  const retryPreview = async () => {
    await preview.refetch();
  };

  if (isScreenshot) {
    return (
      <Card>
        <CardContent className="p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate font-medium text-sm">
                {artifact.name}
              </span>
              <Badge variant="outline">{typeLabels[artifact.type]}</Badge>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {canPreview ? (
                <Button
                  onClick={onPreview}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <Eye />
                  查看
                </Button>
              ) : null}
              {allowDownload ? (
                <ArtifactDownloadButton artifact={artifact} />
              ) : null}
            </div>
          </div>
          <div className="flex min-h-40 items-center justify-center overflow-auto rounded-md bg-muted text-muted-foreground">
            {loadScreenshot && preview.isLoading ? (
              <div className="text-center">
                <LoaderCircle className="mx-auto mb-2 h-8 w-8 animate-spin opacity-60" />
                <p className="text-xs">正在加载截图...</p>
              </div>
            ) : null}
            {loadScreenshot && previewUnavailable ? (
              <div className="space-y-2 text-center">
                <AlertCircle className="mx-auto h-8 w-8 opacity-60" />
                <p className="text-xs">截图加载失败或链接已过期</p>
                <Button
                  onClick={retryPreview}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <RefreshCw />
                  重新加载
                </Button>
              </div>
            ) : null}
            {loadScreenshot && preview.data ? (
              <img
                alt={artifact.name}
                className="max-h-[78vh] max-w-full object-contain"
                height={1080}
                src={preview.data}
                width={1920}
              />
            ) : null}
            {loadScreenshot ? null : canPreview ? (
              <button
                className="w-full cursor-pointer py-8 text-center"
                onClick={onPreview}
                type="button"
              >
                <FileImage className="mx-auto mb-2 h-12 w-12 opacity-50" />
                <p className="text-xs">点击查看截图</p>
                <p className="text-xs">{artifact.sizeText}</p>
              </button>
            ) : (
              <div className="text-center">
                <FileImage className="mx-auto mb-2 h-12 w-12 opacity-50" />
                <p className="text-xs">截图占位预览</p>
                <p className="text-xs">{artifact.sizeText}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3 p-4">
        <div className="flex min-w-0 items-center gap-3">
          <Icon className="h-8 w-8 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="truncate font-medium text-sm">{artifact.name}</p>
            <p className="text-muted-foreground text-xs">
              {typeLabels[artifact.type]} · {artifact.sizeText}
            </p>
          </div>
        </div>
        {allowDownload && isDownloadableArtifact(artifact) ? (
          <ArtifactDownloadButton artifact={artifact} />
        ) : null}
      </CardContent>
    </Card>
  );
}

export function ArtifactPreviewDialog({
  artifact,
  onOpenChange,
}: {
  artifact: Artifact | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog onOpenChange={onOpenChange} open={Boolean(artifact)}>
      <DialogContent
        className={
          artifact?.type === "screenshot"
            ? "sm:max-w-[96vw] xl:max-w-[1600px]"
            : "sm:max-w-xl"
        }
      >
        <DialogHeader>
          <DialogTitle>证据预览</DialogTitle>
        </DialogHeader>
        {artifact ? (
          <ArtifactPreview
            allowDownload={isDownloadableArtifact(artifact)}
            artifact={artifact}
            key={artifact.id}
            loadScreenshot
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

export function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  const [preview, setPreview] = useState<Artifact | null>(null);

  if (artifacts.length === 0) {
    return <p className="text-muted-foreground text-sm">暂无证据</p>;
  }
  return (
    <>
      <div className="space-y-2">
        {artifacts.map((artifact) => (
          <ArtifactPreview
            allowDownload={isDownloadableArtifact(artifact)}
            artifact={artifact}
            key={artifact.id}
            onPreview={
              artifact.type === "screenshot"
                ? () => setPreview(artifact)
                : undefined
            }
          />
        ))}
      </div>
      <ArtifactPreviewDialog
        artifact={preview}
        onOpenChange={(open) => {
          if (!open) {
            setPreview(null);
          }
        }}
      />
    </>
  );
}
