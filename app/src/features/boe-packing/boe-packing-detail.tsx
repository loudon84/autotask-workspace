import { useQueryClient } from "@tanstack/react-query";
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
import {
  BOE_PACK_MAIN_STAGES,
  BOE_PACK_VOL_UNIT,
  boePackReviewDiffs,
  boePackProgressIndex,
  boePackStageName,
  canEditBoePack,
  canRetryBoePack,
  canSubmitBoePack,
} from "@/features/boe-packing/boe-packing-model";
import { autotaskApi } from "@/services/autotask-api";
import { queryKeys } from "@/services/query-keys";
import type { BoePackDetail, BoePackHeader, BoePackLine } from "@/types/boe-packing";

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
    </div>
  );
}

export function BoePackingDetailPage({ instanceId }: { instanceId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch } = useBoePackingDetail(instanceId);
  const [header, setHeader] = useState<BoePackHeader>({});
  const [lines, setLines] = useState<BoePackLine[]>([]);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    if (!data) {
      return;
    }
    setHeader(data.header ?? {});
    setLines(data.lines ?? []);
  }, [data]);

  if (isLoading || !data) {
    return <MockLoading />;
  }

  const editable = canEditBoePack(data.stage);
  const reviewDiffs = boePackReviewDiffs(data.reviewBaseline, header, lines);
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
    <div className="space-y-6">
      <PageHeader
        actions={
          <div className="flex flex-wrap gap-2">
            {canRetryBoePack(data.stage) ? (
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
                onClick={() =>
                  run("已保存", () =>
                    autotaskApi.boePacking.patch(instanceId, { header, lines })
                  )
                }
              >
                保存修改
              </Button>
            ) : null}
            {canSubmitBoePack(data.stage) ? (
              <Button
                disabled={acting || Boolean(data.qtyMismatch)}
                onClick={() =>
                  run("已提交", () => autotaskApi.boePacking.submit(instanceId))
                }
              >
                提交 SRM 单据
              </Button>
            ) : null}
            {data.status === "ACTIVE" ? (
              <Button
                disabled={acting}
                variant="destructive"
                onClick={() => {
                  if (!window.confirm("确认作废？仅更新本地状态。")) {
                    return;
                  }
                  void run("已作废", () =>
                    autotaskApi.boePacking.cancel(instanceId)
                  );
                }}
              >
                作废
              </Button>
            ) : null}
          </div>
        }
        description={data.bizKey}
        title="发票箱单详情"
      />
      <StageProgress detail={data} />
      {data.qtyWarning ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {data.qtyWarning}
        </div>
      ) : null}
      {data.orgCodeWarning ? (
        <div className="rounded-md border px-3 py-2 text-sm">{data.orgCodeWarning}</div>
      ) : null}
      {data.lastErrorMessage ? (
        <div className="rounded-md border border-destructive/40 px-3 py-2 text-sm">
          {data.lastErrorMessage}
        </div>
      ) : null}
      {canSubmitBoePack(data.stage) ? (
        <Card>
          <CardHeader>
            <CardTitle>相对保存草稿基线的变更</CardTitle>
          </CardHeader>
          <CardContent>
            {reviewDiffs.length === 0 ? (
              <p className="text-muted-foreground text-sm">无差异，提交时只点 SRM 提交。</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>字段</TableHead>
                    <TableHead>基线</TableHead>
                    <TableHead>当前</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reviewDiffs.map((diff) => (
                    <TableRow key={diff.path}>
                      <TableCell>{diff.label}</TableCell>
                      <TableCell>{display(diff.before)}</TableCell>
                      <TableCell>{display(diff.after)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <ReadField label="启用 AI 识别" value="否" />
          <EditField
            editable={editable}
            label="供应商发票号"
            onChange={(value) => setHeader({ ...header, invoiceNo: value })}
            value={header.invoiceNo ?? ""}
          />
          <EditField
            editable={editable}
            label="BOE 工厂"
            onChange={(value) => setHeader({ ...header, factory: value })}
            value={header.factory ?? ""}
          />
          <ReadField label="客户名称" value={display(header.customerName)} />
          <ReadField label="客户子代码" value={display(header.customerSubcode)} />
          <ReadField label="交易主体" value={display(header.businessEntity)} />
          <EditField
            editable={editable}
            label="开票日期"
            onChange={(value) => setHeader({ ...header, invoiceDate: value })}
            value={header.invoiceDate ?? ""}
          />
          <EditField
            editable={editable}
            label="ETD"
            onChange={(value) => setHeader({ ...header, etd: value })}
            value={header.etd ?? ""}
          />
          <EditField
            editable={editable}
            label="委托到货日期"
            onChange={(value) =>
              setHeader({ ...header, consignArrivalDate: value })
            }
            value={header.consignArrivalDate ?? ""}
          />
          <EditField
            editable={editable}
            label="总体积"
            onChange={(value) => setHeader({ ...header, totalVol: value })}
            value={header.totalVol ?? ""}
          />
          <ReadField label="单位（体积）" value={BOE_PACK_VOL_UNIT} />
          {data.srmDraftNo ? (
            <ReadField label="SRM 草稿流水号" value={data.srmDraftNo} />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>项目信息</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>PO</TableHead>
                <TableHead>客户料号</TableHead>
                <TableHead>本次开票数</TableHead>
                <TableHead>净重</TableHead>
                <TableHead>地区编号</TableHead>
                <TableHead>SRM 地区</TableHead>
                <TableHead>行项目</TableHead>
                <TableHead>剩余开票数</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line, index) => (
                <TableRow key={`${line.poNum}-${line.itemNum}-${index}`}>
                  <TableCell>{display(line.poNum)}</TableCell>
                  <TableCell>{display(line.itemNum)}</TableCell>
                  <TableCell>
                    {editable ? (
                      <Input
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
                  <TableCell className={!line.regionSrmName ? "text-destructive" : ""}>
                    {display(line.regionCode)}
                  </TableCell>
                  <TableCell className={!line.regionSrmName ? "text-destructive" : ""}>
                    {display(line.regionSrmName)}
                  </TableCell>
                  <TableCell>{display(line.lineItem)}</TableCell>
                  <TableCell>{display(line.remainingQty)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <div className="text-sm">{value}</div>
    </div>
  );
}

function EditField({
  label,
  value,
  editable,
  onChange,
}: {
  label: string;
  value: string;
  editable: boolean;
  onChange: (value: string) => void;
}) {
  if (!editable) {
    return <ReadField label={label} value={display(value)} />;
  }
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input onChange={(event) => onChange(event.target.value)} value={value} />
    </div>
  );
}
