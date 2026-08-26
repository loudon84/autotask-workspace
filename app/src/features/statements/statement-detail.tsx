import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { selectInvoiceFiles } from "@/actions/shell";
import { MAX_INVOICE_FILE_COUNT } from "@/ipc/shell/schemas";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ProcessSubTaskTree } from "@/features/processes/process-subtask-tree";
import { useStatement } from "@/features/statements/api/use-statements";
import { SdmsCheckLabel } from "@/features/statements/sdms-check-label";
import {
  CHECK_STATUS_LABEL,
  INVOICE_STATUS_LABEL,
  RECEIPT_LINE_FIELD_COLUMNS,
  STATEMENT_SUBTASK_NODES,
  formatAmount,
  resolvePersistedStage,
  resolveStatementBlocker,
  statementStageName,
  statementStatusLabel,
} from "@/features/statements/statement-model";
import { StatementSopProgress } from "@/features/statements/statement-sop-progress";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { ProcessSubTask } from "@/types/process-instance";
import { formatBeijingDateTime } from "@/utils/date-time";

function lineCellText(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "-";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type SelectedInvoiceFile = {
  name: string;
  path: string;
  size: number;
};

function storedFileName(filePath: string): string {
  return filePath.split(/[/\\]/).pop() || filePath;
}

function filesFromPaths(paths: string[]): SelectedInvoiceFile[] {
  return paths.map((path) => ({
    name: storedFileName(path),
    path,
    size: 0,
  }));
}

function mergeInvoiceFiles(
  existing: SelectedInvoiceFile[],
  incoming: SelectedInvoiceFile[],
  maxCount: number
): {
  files: SelectedInvoiceFile[];
  added: number;
  skippedDuplicate: number;
  skippedLimit: number;
} {
  const files = [...existing];
  const seen = new Set(existing.map((file) => file.path));
  let added = 0;
  let skippedDuplicate = 0;
  let skippedLimit = 0;
  for (const file of incoming) {
    if (seen.has(file.path)) {
      skippedDuplicate += 1;
      continue;
    }
    if (files.length >= maxCount) {
      skippedLimit += 1;
      continue;
    }
    seen.add(file.path);
    files.push(file);
    added += 1;
  }
  return { files, added, skippedDuplicate, skippedLimit };
}

export function StatementDetailPage({ billId }: { billId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch } = useStatement(billId);
  const [selectedFiles, setSelectedFiles] = useState<
    SelectedInvoiceFile[] | null
  >(null);
  const [acting, setActing] = useState(false);

  if (isLoading) {
    return <MockLoading />;
  }
  if (!data) {
    return <div className="text-muted-foreground text-sm">对账单不存在</div>;
  }

  const stage = resolvePersistedStage(data);
  const cancelled = stage === "STMT_CANCELLED";
  const needsInvoiceWorkspace =
    stage === "STMT_PENDING_INVOICE" || stage === "STMT_PENDING_REVIEW";
  const canRetryGenerate = stage === "STMT_GENERATING";
  const canCancel =
    stage === "STMT_GENERATING" ||
    stage === "STMT_PENDING_INVOICE" ||
    stage === "STMT_PENDING_REVIEW";
  const blocker = resolveStatementBlocker({
    stage,
    instanceStatus: data.instanceStatus,
    lastError: data.lastError,
    lastErrorCode: data.lastErrorCode,
    subTasks: data.subTasks,
  });
  const blockerMessage = blocker?.message ?? null;
  const subTasks: ProcessSubTask[] = (data.subTasks || []).map((task) => ({
    id: task.id,
    title: task.title,
    taskType: task.taskType,
    status: task.status,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
    lineNumber: task.lineNumber,
  }));

  const scannedPaths = data.scannedFilePaths ?? [];
  const scannedAsFiles = filesFromPaths(scannedPaths);
  const workingFiles = selectedFiles ?? scannedAsFiles;
  const isServerFile = (file: SelectedInvoiceFile) =>
    scannedPaths.includes(file.path);

  const onUpdated = async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.statements.all,
    });
    await refetch();
  };

  const chooseInvoices = async (): Promise<SelectedInvoiceFile[] | null> => {
    try {
      const result = await selectInvoiceFiles();
      if (result.cancelled) {
        return null;
      }
      const merged = mergeInvoiceFiles(
        workingFiles,
        result.files,
        MAX_INVOICE_FILE_COUNT
      );
      setSelectedFiles(merged.files);
      if (merged.skippedLimit > 0) {
        toast.error(`最多 ${MAX_INVOICE_FILE_COUNT} 个发票文件，超出的未加入`);
      } else if (merged.added === 0 && merged.skippedDuplicate > 0) {
        toast.error("所选文件已在列表中");
      }
      return merged.files;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "选择文件失败");
      return null;
    }
  };

  const removeInvoice = async (filePath: string) => {
    const target = workingFiles.find((file) => file.path === filePath);
    if (!target) {
      return;
    }
    if (isServerFile(target)) {
      setActing(true);
      try {
        await autotaskApi.statements.deleteInvoiceFile({
          billId,
          fileName: storedFileName(target.path),
        });
        setSelectedFiles(workingFiles.filter((file) => file.path !== filePath));
        await onUpdated();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "删除失败");
      } finally {
        setActing(false);
      }
      return;
    }
    setSelectedFiles(workingFiles.filter((file) => file.path !== filePath));
  };

  const retryGenerate = async () => {
    setActing(true);
    try {
      await autotaskApi.statements.retryGenerate(billId);
      toast.success("已重新发起 SRM 生成");
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重新生成失败");
    } finally {
      setActing(false);
    }
  };

  const cancelStatement = async () => {
    if (!window.confirm("确认取消对账？仅更新本地状态。")) {
      return;
    }
    setActing(true);
    try {
      await autotaskApi.statements.cancel(billId);
      toast.success("已作废");
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "取消失败");
    } finally {
      setActing(false);
    }
  };

  const scanInvoice = async (files?: SelectedInvoiceFile[]) => {
    const targets = files ?? workingFiles;
    if (targets.length === 0) {
      const picked = await chooseInvoices();
      if (!picked || picked.length === 0) {
        toast.error("请先选择发票文件");
        return;
      }
      await scanInvoice(picked);
      return;
    }
    const localFiles = targets.filter((file) => !isServerFile(file));
    setActing(true);
    try {
      if (localFiles.length > 0) {
        await autotaskApi.statements.uploadInvoiceFiles({
          billId,
          filePaths: localFiles.map((file) => file.path),
        });
      } else {
        await autotaskApi.statements.rescanInvoice(billId);
      }
      setSelectedFiles(null);
      toast.success("已发起扫描发票：完成后请核对发票号和发票总额");
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "扫描失败");
    } finally {
      setActing(false);
    }
  };

  const submitReview = async () => {
    if (workingFiles.length === 0) {
      toast.error("请先选择发票并扫描");
      return;
    }
    if (!data.invoiceNo || data.invoiceAmount == null || data.invoiceAmount === "") {
      toast.error("请先扫描发票，并核对页面上的发票号和发票总额");
      return;
    }
    setActing(true);
    try {
      await autotaskApi.statements.submitReview(billId);
      toast.success("已发起提交审核：将再次扫描并核对后提交");
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "提交失败");
    } finally {
      setActing(false);
    }
  };

  const selectedPathKey = workingFiles.map((file) => file.path).join("|");
  const scannedPathKey = scannedPaths.join("|");
  const filesChanged =
    selectedFiles !== null && selectedPathKey !== scannedPathKey;
  const hasVerifiedInvoice = Boolean(data.invoiceNo && data.invoiceAmount);
  const canScan = workingFiles.length > 0;
  const canSubmit = hasVerifiedInvoice && workingFiles.length > 0 && !filesChanged;

  return (
    <div className="space-y-4">
      <PageHeader
        description="天地伟业对账单 SOP"
        title={`对账单 ${data.checkDate} / ${formatAmount(data.checkAmount)}`}
      >
        <div className="flex flex-wrap gap-2">
          {canRetryGenerate ? (
            <Button disabled={acting} onClick={() => void retryGenerate()}>
              重新生成
            </Button>
          ) : null}
          {needsInvoiceWorkspace ? (
            <>
              <Button
                disabled={acting || !canScan}
                onClick={() => void scanInvoice()}
                variant="outline"
              >
                扫描发票
              </Button>
              <Button
                disabled={acting || !canSubmit}
                onClick={() => void submitReview()}
              >
                提交审核
              </Button>
            </>
          ) : null}
          {canCancel ? (
            <Button
              disabled={acting}
              onClick={() => void cancelStatement()}
              variant="outline"
            >
              取消对账
            </Button>
          ) : null}
          <Button asChild size="sm" variant="outline">
            <Link to="/process-instances/statements">返回列表</Link>
          </Button>
        </div>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        <Badge className="text-sm" variant="default">
          阶段：{statementStageName(stage)}
        </Badge>
        <Badge className="text-sm" variant="secondary">
          运行状态：{statementStatusLabel(data.instanceStatus)}
        </Badge>
      </div>

      {blockerMessage ? (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm"
          role="status"
        >
          <p className="font-medium text-destructive">当前阶段阻塞</p>
          <p className="mt-1">{blockerMessage}</p>
          {blocker?.errorCode ? (
            <p className="text-muted-foreground mt-1 text-xs">
              错误码：{blocker.errorCode}
            </p>
          ) : null}
          <p className="text-muted-foreground mt-1 text-xs">
            可在下方「子任务与执行记录」查看详情；阶段未变时可重试对应操作。
          </p>
        </div>
      ) : null}

      {canRetryGenerate && !blockerMessage ? (
        <p className="text-muted-foreground text-sm">
          待生成草稿已落库，SRM 生成进行中。本页会自动刷新；失败后可重新生成。
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">流程进度</CardTitle>
        </CardHeader>
        <CardContent>
          <StatementSopProgress
            cancelled={cancelled}
            currentStep={cancelled ? "STMT_GENERATING" : stage}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">基本信息</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3 text-sm">
          <div>对账日期：{data.checkDate}</div>
          <div>
            对账状态：
            <Badge className="ml-1" variant="outline">
              {CHECK_STATUS_LABEL[data.checkStatus]}
            </Badge>
          </div>
          <div>
            发票状态：
            {INVOICE_STATUS_LABEL[data.invoiceStatus] ?? data.invoiceStatus}
          </div>
          <div>对账总额：¥{formatAmount(data.checkAmount)}</div>
          <div>发票总额：¥{formatAmount(data.invoiceAmount)}</div>
          <div>发票号：{data.invoiceNo || "-"}</div>
          <div className="md:col-span-3">
            <SdmsCheckLabel
              checkHeadId={data.sdmsCheckHeadId}
              checkNum={data.sdmsCheckNum}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            对账明细（{data.lines?.length ?? 0} 行）
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(data.lines?.length ?? 0) === 0 ? (
            <p className="text-muted-foreground text-sm">
              暂无对账明细。生成时勾选的收货行会显示在这里。
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {RECEIPT_LINE_FIELD_COLUMNS.map((column) => (
                      <TableHead
                        className="whitespace-nowrap"
                        key={String(column.accessorKey)}
                      >
                        {column.header}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data.lines ?? []).map((line, index) => (
                    <TableRow
                      key={`${String(line.receiptNo)}-${String(line.lineNo)}-${index}`}
                    >
                      {RECEIPT_LINE_FIELD_COLUMNS.map((column) => {
                        const value = line[column.accessorKey];
                        return (
                          <TableCell
                            className="whitespace-nowrap"
                            key={String(column.accessorKey)}
                          >
                            {column.format === "amount"
                              ? formatAmount(value as string)
                              : lineCellText(value)}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {needsInvoiceWorkspace ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">扫描发票并提交审核</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-muted-foreground text-sm">
              可分多次选择发票，列表里可删除单张。先扫描，在上方核对发票号和发票总额。点「提交审核」表示已核对通过；RPA
              会用同一批文件再扫一次，必须与页面结果一致才会提交。门户刷新后附件可能消失，这是预期。最多{" "}
              {MAX_INVOICE_FILE_COUNT}{" "}
              个文件，支持 png、jpg、jpeg、pdf、ofd，单个不超过 20MB。
            </p>
            {filesChanged ? (
              <p className="text-sm text-destructive">
                发票文件已更换，请先重新扫描，再提交审核。
              </p>
            ) : null}
            {workingFiles.length > 0 ? (
              <ul className="rounded-md border px-3 py-2 text-sm">
                {workingFiles.map((file) => (
                  <li
                    className="flex items-center justify-between gap-3 py-1"
                    key={file.path}
                  >
                    <span className="truncate">{file.name}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      {file.size > 0 ? (
                        <span className="text-muted-foreground text-xs">
                          {formatFileSize(file.size)}
                        </span>
                      ) : null}
                      <Button
                        aria-label={`删除 ${file.name}`}
                        disabled={acting}
                        onClick={() => removeInvoice(file.path)}
                        size="icon-sm"
                        type="button"
                        variant="ghost"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={acting}
                onClick={() => void chooseInvoices()}
                variant="outline"
              >
                选择发票
              </Button>
              <Button
                disabled={acting || !canScan}
                onClick={() => void scanInvoice()}
              >
                扫描发票
              </Button>
              <Button
                disabled={acting || !canSubmit}
                onClick={() => void submitReview()}
              >
                提交审核
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">子任务与执行记录</CardTitle>
        </CardHeader>
        <CardContent>
          <ProcessSubTaskTree
            nodeOrder={STATEMENT_SUBTASK_NODES}
            tasks={subTasks}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">阶段历史</CardTitle>
        </CardHeader>
        <CardContent>
          {(data.stageHistory || []).length === 0 ? (
            <p className="text-muted-foreground text-sm">暂无阶段历史</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间（北京时间）</TableHead>
                  <TableHead>从</TableHead>
                  <TableHead>到</TableHead>
                  <TableHead>操作者</TableHead>
                  <TableHead>备注</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data.stageHistory || []).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      {formatBeijingDateTime(item.createdAt)}
                    </TableCell>
                    <TableCell>
                      {statementStageName(item.fromStage) === "—"
                        ? "—"
                        : statementStageName(item.fromStage)}
                    </TableCell>
                    <TableCell>{statementStageName(item.toStage)}</TableCell>
                    <TableCell>{item.actor}</TableCell>
                    <TableCell>{item.note ?? ""}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
