import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useBoePackingDetail } from "@/features/boe-packing/api/use-boe-packing";
import { selectInvoiceFiles } from "@/actions/shell";
import {
  BOE_PACK_ATTACH_TYPES,
  BOE_PACK_MAIN_STAGES,
  BOE_PACK_SUBTASK_NODES,
  BOE_PACK_NET_WEIGHT_UNIT,
  BOE_PACK_VOL_UNIT,
  boePackAttachmentErrors,
  boePackRequiredErrors,
  boePackProgressIndex,
  boePackRunStatus,
  boePackStageName,
  canEditBoePack,
  canRetryBoePack,
  canSubmitBoePack,
  compactBoeDecimal,
  defaultBoePackAttachments,
  isFixedBoePackAttachment,
  latestBoePackTaskStatus,
  normalizeBoePackAttachments,
  resolveBoePackBlocker,
} from "@/features/boe-packing/boe-packing-model";
import { SdmsDeliveryPlanLabel } from "@/features/boe-packing/sdms-delivery-plan-label";
import { ProcessSubTaskTree } from "@/features/processes/process-subtask-tree";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type {
  BoePackAttachment,
  BoePackDetail,
  BoePackHeader,
  BoePackLine,
} from "@/types/boe-packing";
import type { ProcessSubTask } from "@/types/process-instance";
import { formatBeijingDateTime } from "@/utils/date-time";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function StageProgress({ detail }: { detail: BoePackDetail }) {
  const currentIndex = boePackProgressIndex(detail.stage);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {BOE_PACK_MAIN_STAGES.map((stage, index) => {
        const reached = currentIndex >= index;
        const isCurrent = currentIndex === index && detail.status === "ACTIVE";
        return (
          <div className="flex items-center gap-2" key={stage}>
            {index > 0 && <div className="h-px w-6 bg-border" />}
            <div
              className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${
                isCurrent
                  ? "border-primary text-primary"
                  : reached
                    ? "border-primary/40 text-foreground"
                    : "text-muted-foreground"
              }`}
            >
              {reached && !isCurrent && <Check className="h-3 w-3" />}
              {boePackStageName(stage)}
            </div>
          </div>
        );
      })}
      {detail.stage === "BOE_PACK_CANCELLED" && (
        <Badge variant="destructive">已作废</Badge>
      )}
      {detail.stage === "BOE_PACK_DELETING_DRAFT" && (
        <Badge variant="secondary">删除 SRM 草稿</Badge>
      )}
    </div>
  );
}

export function BoePackingDetailPage({ instanceId }: { instanceId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch } = useBoePackingDetail(instanceId);
  const [header, setHeader] = useState<BoePackHeader>({});
  const [lines, setLines] = useState<BoePackLine[]>([]);
  const [attachments, setAttachments] = useState<BoePackAttachment[]>([]);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    if (!data) {
      return;
    }
    setHeader({
      ...(data.header ?? {}),
      totalVol: compactBoeDecimal(data.header?.totalVol) || data.header?.totalVol || "",
    });
    const nextLines = (data.lines ?? []).map((line) => ({
      ...line,
      netWeight: compactBoeDecimal(line.netWeight) || line.netWeight || "",
    }));
    setLines(nextLines);
    setAttachments(
      normalizeBoePackAttachments(
        data.attachments && data.attachments.length > 0
          ? data.attachments
          : defaultBoePackAttachments(nextLines)
      )
    );
  }, [data]);

  if (isLoading || !data) {
    return <MockLoading />;
  }

  const runStatus = boePackRunStatus({
    status: data.status,
    lastErrorMessage: data.lastErrorMessage,
    latestTaskStatus: latestBoePackTaskStatus(data.subTasks),
  });
  const editable = canEditBoePack(data.stage);
  const blocker = resolveBoePackBlocker({
    stage: data.stage,
    instanceStatus: data.status,
    lastError: data.lastErrorMessage,
    lastErrorCode: data.lastErrorCode,
    subTasks: data.subTasks,
  });
  const subTasks: ProcessSubTask[] = (data.subTasks || []).map((task) => ({
    id: task.id,
    title: task.title,
    taskType: task.taskType,
    status: task.status,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
    lineNumber: task.lineNumber,
  }));
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.boePacking.all });
    await refetch();
  };

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setActing(true);
    try {
      await fn();
      toast.success(label);
      await refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : label);
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader description={data.bizKey} title="发票箱单详情">
        <div className="flex flex-wrap gap-2">
            {canRetryBoePack({
              stage: data.stage,
              lastErrorMessage: data.lastErrorMessage,
              latestTaskStatus: latestBoePackTaskStatus(data.subTasks),
            }) ? (
              <Button
                disabled={acting}
                onClick={() =>
                  run("已重试", () => autotaskApi.boePacking.retry(instanceId))
                }
              >
                重试
              </Button>
            ) : null}
            {editable ? (
              <Button
                disabled={acting}
                variant="outline"
                onClick={() => {
                  const required = boePackRequiredErrors(header, lines);
                  if (required.length) {
                    toast.error(required[0]);
                    return;
                  }
                  void run("已保存", () =>
                    autotaskApi.boePacking.patch(instanceId, {
                      header,
                      lines,
                      attachments,
                    })
                  );
                }}
              >
                保存修改
              </Button>
            ) : null}
            {canSubmitBoePack(data.stage) ? (
              <Button
                disabled={acting || Boolean(data.qtyMismatch)}
                onClick={() => {
                  const required = boePackRequiredErrors(header, lines);
                  if (required.length) {
                    toast.error(required[0]);
                    return;
                  }
                  const attach = boePackAttachmentErrors(
                    header.invoiceNo ?? "",
                    lines,
                    attachments
                  );
                  if (attach.length) {
                    toast.error(attach[0]);
                    return;
                  }
                  if (
                    !window.confirm(
                      "dryRun=true：会把核验改动和附件写到 SRM 草稿并保存。\n" +
                        "不会点「提交」，单据仍可继续改。\n" +
                        "确认继续吗？"
                    )
                  ) {
                    return;
                  }
                  void run("已发起演练保存", async () => {
                    await autotaskApi.boePacking.patch(instanceId, {
                      header,
                      lines,
                      attachments,
                    });
                    return autotaskApi.boePacking.submit(instanceId);
                  });
                }}
              >
                提交 SRM 单据
              </Button>
            ) : null}
            {data.status === "ACTIVE" && data.stage !== "BOE_PACK_DELETING_DRAFT" ? (
              <Button
                disabled={acting}
                variant="destructive"
                onClick={() => {
                  const hasDraft = Boolean((data.srmDraftNo ?? "").trim());
                  const ok = window.confirm(
                    hasDraft
                      ? "确认作废？将先删除 SRM 草稿，成功后再改本地状态。"
                      : "确认作废？尚无 SRM 草稿，只改本地状态。"
                  );
                  if (!ok) {
                    return;
                  }
                  void run(hasDraft ? "已发起删除 SRM 草稿" : "已作废", () =>
                    autotaskApi.boePacking.cancel(instanceId)
                  );
                }}
              >
                作废
              </Button>
            ) : null}
            <Button asChild size="sm" variant="outline">
              <Link to="/process-instances/invoice-packing">返回列表</Link>
            </Button>
          </div>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        <Badge className="text-sm" variant="default">
          阶段：{boePackStageName(data.stage)}
        </Badge>
        <Badge className="text-sm" variant={runStatus.variant}>
          运行状态：{runStatus.label}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">流程进度</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <StageProgress detail={data} />
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">
            <ReadField label="发票箱单流水号" value={(data.srmDraftNo ?? "").trim() || "—"} />
            <ReadField label="客户名称" value={display(header.customerName)} />
            <ReadField label="客户子代码" value={display(header.customerSubcode)} />
            <ReadField label="交易主体" value={display(header.businessEntity)} />
            <SdmsDeliveryPlanLabel
              docNo={data.bizKey}
              headerId={data.headerId}
            />
          </div>
        </CardContent>
      </Card>
      {data.qtyWarning ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {data.qtyWarning}
        </div>
      ) : null}
      {data.orgCodeWarning ? (
        <div className="rounded-md border px-3 py-2 text-sm">{data.orgCodeWarning}</div>
      ) : null}
      {blocker ? (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm"
          role="status"
        >
          <p className="font-medium text-destructive">{blocker.title}</p>
          <p className="mt-1">{blocker.message}</p>
          {blocker.errorCode ? (
            <p className="text-muted-foreground mt-1 text-xs">
              错误码：{blocker.errorCode}
            </p>
          ) : null}
          <p className="text-muted-foreground mt-1 text-xs">
            可在下方「子任务与执行记录」查看详情；处理完后可点右上角「重试」。
          </p>
        </div>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">基本信息</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3 text-sm">
          <ReadField label="启用 AI 识别" value="否" />
          <EditField
            editable={editable}
            label="供应商发票号"
            required
            onChange={(value) => setHeader({ ...header, invoiceNo: value })}
            value={header.invoiceNo ?? ""}
          />
          <EditField
            editable={editable}
            label="BOE 工厂"
            required
            onChange={(value) => setHeader({ ...header, factory: value })}
            value={header.factory ?? ""}
          />
          <EditField
            editable={editable}
            label="开票日期"
            required
            onChange={(value) => setHeader({ ...header, invoiceDate: value })}
            value={header.invoiceDate ?? ""}
          />
          <EditField
            editable={editable}
            label="ETD"
            required
            onChange={(value) => setHeader({ ...header, etd: value })}
            value={header.etd ?? ""}
          />
          <EditField
            editable={editable}
            label="委托到货日期"
            required
            onChange={(value) =>
              setHeader({ ...header, consignArrivalDate: value })
            }
            value={header.consignArrivalDate ?? ""}
          />
          <EditField
            editable={editable}
            label="总体积"
            required
            onChange={(value) => setHeader({ ...header, totalVol: value })}
            value={header.totalVol ?? ""}
          />
          <ReadField label="单位（体积）" value={BOE_PACK_VOL_UNIT} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            项目信息（{lines.length} 行）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-muted-foreground text-xs">
            客户 PO、客户料号固定在左侧，其余列可左右拖动。本次开票数、净重可改；净重单位取不到时固定「千克」。行项目 / 订单数量 / 订单单位 / 剩余开票数由 RPA 从 SRM 带回。
          </p>
          <Table className="min-w-[1180px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky left-0 z-20 min-w-36 bg-background shadow-[1px_0_0_0_hsl(var(--border))]">
                    客户PO
                  </TableHead>
                  <TableHead className="sticky left-36 z-20 min-w-32 bg-background shadow-[1px_0_0_0_hsl(var(--border))]">
                    客户料号
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    {editable ? <RequiredMark label="本次开票数" /> : "本次开票数"}
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    {editable ? <RequiredMark label="净重" /> : "净重"}
                  </TableHead>
                  <TableHead className="whitespace-nowrap">净重单位</TableHead>
                  <TableHead className="whitespace-nowrap">地区编号</TableHead>
                  <TableHead className="whitespace-nowrap">SRM 地区</TableHead>
                  <TableHead className="whitespace-nowrap">行项目</TableHead>
                  <TableHead className="whitespace-nowrap">订单数量</TableHead>
                  <TableHead className="whitespace-nowrap">订单单位</TableHead>
                  <TableHead className="whitespace-nowrap">剩余开票数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.map((line, index) => (
                  <TableRow key={`${line.poNum}-${line.itemNum}-${index}`}>
                    <TableCell className="sticky left-0 z-10 min-w-36 bg-background shadow-[1px_0_0_0_hsl(var(--border))]">
                      {display(line.poNum)}
                    </TableCell>
                    <TableCell className="sticky left-36 z-10 min-w-32 bg-background shadow-[1px_0_0_0_hsl(var(--border))]">
                      {display(line.itemNum)}
                    </TableCell>
                    <TableCell>
                      {editable ? (
                        <Input
                          className="h-8 w-24"
                          value={line.deliveryQty ?? ""}
                          onChange={(event) => {
                            const next = [...lines];
                            next[index] = {
                              ...line,
                              deliveryQty: event.target.value,
                            };
                            setLines(next);
                          }}
                        />
                      ) : (
                        display(line.deliveryQty)
                      )}
                    </TableCell>
                    <TableCell>
                      {editable ? (
                        <Input
                          className="h-8 w-24"
                          value={line.netWeight ?? ""}
                          onChange={(event) => {
                            const next = [...lines];
                            next[index] = {
                              ...line,
                              netWeight: event.target.value,
                            };
                            setLines(next);
                          }}
                        />
                      ) : (
                        display(line.netWeight)
                      )}
                    </TableCell>
                    <TableCell>
                      {(line.netWeightUnit || "").trim() || BOE_PACK_NET_WEIGHT_UNIT}
                    </TableCell>
                    <TableCell className={!line.regionSrmName ? "text-destructive" : ""}>
                      {display(line.regionCode)}
                    </TableCell>
                    <TableCell className={!line.regionSrmName ? "text-destructive" : ""}>
                      {display(line.regionSrmName)}
                    </TableCell>
                    <TableCell>{display(line.lineItem)}</TableCell>
                    <TableCell>{display(line.orderQty)}</TableCell>
                    <TableCell>{display(line.orderUnit)}</TableCell>
                    <TableCell>{display(line.remainingQty)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">附件信息（客服核验上传）</CardTitle>
          {editable ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setAttachments([
                  ...attachments,
                  {
                    id: `att-${Date.now()}`,
                    type: "双签PO/协议",
                    fileName: "",
                    filePath: "",
                  },
                ])
              }
            >
              新增行
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-muted-foreground text-xs">
            前三行固定为箱单、发票、提运单（与 SRM 一致，不能删、不能换序）。双签在保存草稿时已从 SRM 删掉，核验按 PO 份数新增行再传。箱单建议 PL-发票号.pdf，硬限制是文件名包含 pl；发票：发票号.pdf；提运单可不传；双签每个采购订单号一份，文件名为 PO 号。
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>文件类型</TableHead>
                  <TableHead>文件</TableHead>
                  {editable ? <TableHead className="w-28">操作</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {attachments.map((row, index) => {
                  const fixed = isFixedBoePackAttachment(row.type);
                  return (
                    <TableRow key={row.id || `${row.type}-${index}`}>
                      <TableCell>
                        {editable && !fixed ? (
                          <select
                            className="border-input h-8 rounded-md border bg-transparent px-2 text-sm"
                            value={row.type || "双签PO/协议"}
                            onChange={(event) => {
                              const next = [...attachments];
                              next[index] = { ...row, type: event.target.value };
                              setAttachments(next);
                            }}
                          >
                            {BOE_PACK_ATTACH_TYPES.filter(
                              (item) => !isFixedBoePackAttachment(item)
                            ).map((item) => (
                              <option key={item} value={item}>
                                {item}
                              </option>
                            ))}
                          </select>
                        ) : (
                          display(row.type)
                        )}
                      </TableCell>
                      <TableCell>{display(row.fileName)}</TableCell>
                      {editable ? (
                        <TableCell className="space-x-2 whitespace-nowrap">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              void (async () => {
                                try {
                                  const result = await selectInvoiceFiles();
                                  if (result.cancelled || result.files.length === 0) {
                                    return;
                                  }
                                  const file = result.files[0];
                                  if (!file.name.toLowerCase().endsWith(".pdf")) {
                                    toast.error("附件必须是 PDF");
                                    return;
                                  }
                                  const next = [...attachments];
                                  next[index] = {
                                    ...row,
                                    fileName: file.name,
                                    filePath: file.path,
                                  };
                                  setAttachments(next);
                                } catch (error) {
                                  toast.error(
                                    error instanceof Error ? error.message : "选择文件失败"
                                  );
                                }
                              })();
                            }}
                          >
                            选择文件
                          </Button>
                          {fixed ? null : (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                setAttachments(
                                  attachments.filter((_, idx) => idx !== index)
                                )
                              }
                            >
                              删除
                            </Button>
                          )}
                        </TableCell>
                      ) : null}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">子任务与执行记录</CardTitle>
        </CardHeader>
        <CardContent>
          <ProcessSubTaskTree nodeOrder={BOE_PACK_SUBTASK_NODES} tasks={subTasks} />
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
                    <TableCell>{formatBeijingDateTime(item.createdAt)}</TableCell>
                    <TableCell>
                      {item.fromStage ? boePackStageName(item.fromStage) : "—"}
                    </TableCell>
                    <TableCell>{boePackStageName(item.toStage)}</TableCell>
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

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}：</span>
      {value}
    </div>
  );
}

function RequiredMark({ label }: { label: string }) {
  return (
    <span>
      <span className="text-destructive">*</span>
      {label}
    </span>
  );
}

function EditField({
  label,
  value,
  editable,
  required,
  onChange,
}: {
  label: string;
  value: string;
  editable: boolean;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  if (!editable) {
    return <ReadField label={label} value={display(value)} />;
  }
  return (
    <div className="space-y-1">
      <Label className="text-muted-foreground text-xs">
        {required ? <RequiredMark label={label} /> : label}
      </Label>
      <Input
        className="h-8 text-sm"
        onChange={(event) => onChange(event.target.value)}
        required={required}
        value={value}
      />
    </div>
  );
}
