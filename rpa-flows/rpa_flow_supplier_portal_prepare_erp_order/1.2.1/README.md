# 供应商门户订单下载并推送 ERP Flow

版本：`1.2.1`

本 Flow 使用 Engine 托管的 Playwright 浏览器登录供应商门户，按输入的客户采购订单号进入普通订单详情页或待签章订单详情页，下载对应 XLSX 附件，按既定映射构造 ERP 销售订单报文，获取 OAuth Access Token，并向预配置的 ERP 销售订单导入端点提交一次请求。

> 写操作警告：本版本会产生外部 ERP 写入。未经明确批准，不得把 WorkflowBinding 切换到本版本，也不得对结果不明确的订单自动重试。

## 输入契约

Flow 只接收一个必填输入：

```json
{
  "po_no": "POJS2606030010"
}
```

供应商门户地址来自任务 Binding 的 `config.portalUrl`，由 Runtime 暴露为 `ctx.portal_url`。本地调试器必须显式提供对应地址。

## 页面兼容和重试边界

1. 订单列表的详情入口可能进入普通详情路由，也可能进入 `/#/supplier/pend-orders/{po_no}` 待签章详情路由；Flow 会同时校验两类页面的订单号、明细表和下载入口。
2. 待签章详情页使用订单专属下载文件时，仍必须通过相同 XLSX 安全检查、字段校验和订单号一致性检查。
3. Runtime 复用已登录浏览器会话时，登录步骤会识别 Dashboard 并继续，不再错误等待验证码元素。
4. 已登录会话兼容不等于允许自动重推 ERP。由于本 Flow 没有稳定幂等键，受控 Binding/Runtime 必须关闭整段自动重试；结果不明确时只能人工核实后创建新 Run。

## 数据来源和映射边界

1. 页面字段只用于登录、导航和下载附件，不进入 ERP 请求体。
2. ERP 请求字段仅来自 XLSX 映射、已确认的默认值和约定的空字段。
3. XLSX 中每一条订单行都会保留为独立业务明细，顺序不变。
4. `sourceHeaderId` 和 `sourceLineId` 保持为空，因为 XLSX 不提供稳定的源记录 ID；Flow 不生成随机 ID。
5. 税率默认使用 `0.13`，未税单价按含税单价除以 `1 + 0.13` 计算并保留四位小数。

## ERP 成功与失败判定

只有同时满足以下条件才判定业务成功：

- HTTP 状态为 2xx。
- 顶层 `code=2000` 且 `success=true`。
- `rows` 为非空数组。
- 每一行 `processStatusCode=COMPLETE`。
- 每一行均包含非空 ERP `orderNumber`。
- 所有成功行解析为同一个 ERP 订单号。

任一结果行的 `processStatusCode=ERROR` 时，返回业务失败 `ERP_ORDER_IMPORT_ROW_FAILED`，并保留经过长度限制和脱敏处理的行级原因。缺少结果行、未知状态、成功行没有订单号或返回多个不同订单号时，进入 `WAITING_HUMAN / ERP_ORDER_IMPORT_OUTCOME_UNKNOWN`，不得自动再次推送。

认证失败和端点配置错误属于致命失败；提交后的超时、断连、限流、服务端错误、取消或矛盾响应均视为结果不明确并进入人工核实。

## 冻结的成功输出契约

成功时 `run(ctx)` 只返回以下结构：

```json
{
  "schemaVersion": "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
  "poNo": "POJS2606030010",
  "orderNumber": "10108260700027",
  "supplierCode": "02556",
  "supplierName": "深圳市芯云信息科技有限公司",
  "lineCount": 1,
  "lines": [
    {
      "lineNumber": "10",
      "customerItemNumber": "1B.30040.020227",
      "orderQuantity": "31200.0",
      "unitSellingPrice": "22.9448",
      "requestDate": "2026-06-24"
    }
  ]
}
```

`lines` 保留 XLSX 中可用的完整订单业务字段，包括供应商、客户采购订单号、订单行号、客户料号、料品名称与规格、数量、单位、单价、价税合计、交货日期、备注，以及计算得到的 `taxRate` 和 `unTaxPrice`。

成功返回中禁止出现 `draft`、`orderDetail`、`erpPayload`、`erpResponse`、`draftOnly`、`transmitted`、OAuth Token、Authorization Header 或任何凭据字段。

当前 Engine Runtime 尚未保存 Flow 的 Python 返回值，因此同一订单摘要也会写入 `ERP_ORDER_IMPORT_SUCCEEDED` 事件，供现有 Task/Run 查看。后续 Engine 支持结构化 Flow 结果后，应直接保存上述带 `schemaVersion` 的冻结契约。

## 截图和 Artifact

XLSX 下载和截图必须通过 `ctx.artifacts` 记录。生成 `supplier-portal-erp-draft-prepared` 截图前，Flow 会确认：

1. 下载确认弹窗已经消失。
2. 当前普通详情页或待签章详情页、对应下载入口和至少一条订单明细已经可见。
3. 页面加载遮罩已经消失。
4. `document.fonts.ready` 已完成。
5. 详情区域内所有可见图片已经成功加载。
6. 页面布局连续两次检测一致。
7. 最后额外等待约 300ms 完成视觉收敛。

## 凭据和发布限制

根据已批准的私有包例外，本 Flow 的 ERP OAuth 凭据配置在私有 `flow.py` 中。不得把源码或 ZIP 提交到公开仓库、公开制品库或不受控日志，也不得打印具体凭据值。凭据轮换必须重建未发布版本，或发布新的不可变版本并更新 WorkflowBinding。

Access Token、Authorization Header、OAuth 查询参数和原始认证响应不得写入日志、事件、Artifact 或成功输出。

## 幂等限制

XLSX 不提供稳定的源记录 ID，因此 Flow 没有可靠的 ERP 幂等键。`WAITING_HUMAN` 可以降低普通重试风险，但 Worker 在 ERP 已提交后崩溃时，Flow 本身无法保证至多一次。生产启用前仍需 ERP 幂等/查询契约，或 Engine 提交后重试屏障。
