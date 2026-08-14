# 供应商门户订单下载并推送 ERP Flow

版本：`1.2.6`

本 Flow 使用 Engine 托管的 Playwright 页面登录供应商门户，按任务输入的采购订单号进入详情页，下载 XLSX 订单附件，以门户详情的“订单行号 + 客户料号”核对附件明细，核对成功后才构造并提交 ERP 销售订单。

> 写操作警告：本版本会产生外部 ERP 写入。发布不等于启用；未经单独授权不得切换 WorkflowBinding 或运行任务。ERP 提交结果不明确时不得自动重试。

## 1.2.6 变更（相对 1.2.5）

成功输出增加顶层 `headerId`（取自 ERP 导入结果 rows 首个非空 `headerId`），供 AutoTask 流程实例 summary 持久化后拼 SDMS 销售订单查看页链接（`fdId`）。

## 1.2.5 变更（相对 1.2.3）

修复真实供应商门户 Element UI **固定列表格**下读取订单行身份失败的问题：

- 新增 `lines_table` 选择器，等待表格容器而非 `detail_rows.first` 的 `visible` 状态。
- `collect_order_line_identities()` 改为在表格上 `page.evaluate`，使用 `textContent`（兼容 `is-hidden` 列），并按表头匹配「行号 / 客户料号」列。
- `wait_for_detail_stable()` 同步改为等待 `lines_table`，布局稳定性测量也基于 `lines_table` 作用域。

## 输入和运行契约

Flow 只接收一个必填输入：

```json
{
  "po_no": "POJS2607170001"
}
```

- Flow ID：`rpa_flow_supplier_portal_prepare_erp_order`
- Workflow Code：`srm_prepare_erp_order`
- Entry Point：`flow.py:run`
- 成功输出 Schema：`ORDER_DOWNLOAD_PUSH_OUTPUT_V1`
- 门户地址由 Binding 的 `config.portalUrl` 注入；Flow 不启动浏览器，继续使用 `ctx.page`。
- 门户凭据通过 `ctx.credentials` 读取，并兼容 Engine 提供的只读 `MappingProxyType`。

## 1.2.3 明细身份和串单保护

`1.2.3` 以当前门户详情中的以下组合键作为订单明细身份：

```text
订单行号 lineNumber + 客户料号 customerItemNumber
```

对账必须同时满足：

1. 门户详情和 XLSX 都至少有一行。
2. 两边行数完全相同。
3. 门户行号唯一，XLSX 行号唯一。
4. 两边“行号 + 料号”集合完全相同。
5. 同一料号可以出现在不同的唯一行号上。

本版本只兼容 XLSX 中个别明细的订单号 `poNo` 错写。身份集合完全一致后，Flow 会复制每一条 XLSX 明细，将复制结果的 `poNo` 统一规范化为当前任务 `po_no`，并按门户详情顺序输出。原始解析对象不会被修改，数量、单位、价格、金额、要求交货日期、备注及其他 XLSX 字段均保持原值。

严禁按附件订单号过滤明细。错误订单号所在的有效行不会被丢弃；它必须先凭“行号 + 料号”通过完整对账，再仅修正订单号字段。

这不是取消串单保护：

- 缺行、多行、重复行号或料号错误仍会在 ERP OAuth 前失败。
- `POJS2606030010` 这类门户与附件行数、料号均不一致的数据仍会被拒绝。
- 对账失败不会请求 ERP Token，不会调用 ERP 导入，也不会产生成功输出或任务 2 后继条件。

## 执行顺序

```text
登录门户
→ 打开当前订单详情
→ 只读采集门户全部“行号 + 料号”
→ 下载并解析 XLSX
→ 双向完整对账并复制、规范化 poNo
→ 记录 ORDER_ATTACHMENT_RECONCILED
→ 构造 ERP 报文
→ 等待详情页稳定并截图
→ 获取 ERP Token
→ 单次提交 ERP
→ 返回冻结成功输出
```

门户采集只读取表格，不填写预计交货日期，不点击保存或签章，也不创建新的浏览器会话。

## 对账事件

对账成功后记录 `ORDER_ATTACHMENT_RECONCILED`，载荷只包含：

```json
{
  "poNo": "POJS2607170001",
  "portalLineCount": 3,
  "attachmentLineCount": 3,
  "normalizedPoNumberCount": 1
}
```

`normalizedPoNumberCount` 表示附件中需要纠正订单号的行数；附件订单号原本正确时为 `0`。事件不记录原始错误订单号列表、门户凭据或 ERP 凭据。

## 对账错误边界

- `ORDER_DETAIL_LINES_UNAVAILABLE`：门户详情行不可读取、为空或身份字段不完整。
- `ORDER_DETAIL_LINE_DUPLICATE`：门户存在重复行号。
- `ORDER_ATTACHMENT_LINE_COUNT_MISMATCH`：附件与门户行数不同，或附件没有明细。
- `ORDER_ATTACHMENT_LINE_DUPLICATE`：附件存在重复行号。
- `ORDER_ATTACHMENT_LINE_MISMATCH`：行数一致但“行号 + 料号”集合不同，或附件身份字段无效。

错误详情最多包含行号、料号、索引或行数，不包含凭据、Token、完整敏感配置或原始错误订单号列表。失败证据继续由 Engine Runtime 的标准截图和 Trace 机制保留。

## ERP 数据边界

对账完成后，后续步骤只能使用 `normalized_attachment`：

- ERP `lines[].custPoNumber` 全部等于当前任务 `po_no`。
- Task 1 成功输出 `lines[].poNo` 全部等于当前任务 `po_no`。
- 输出 `lineCount` 等于门户详情行数。
- ERP 备注使用规范化附件中的完整业务明细生成。

页面字段只用于登录、导航、明细身份核对和附件下载，不直接映射到 ERP 业务报文。ERP 其他字段继续来自 XLSX、既定默认值和约定空字段；税率默认 `0.13`，未税单价按含税单价除以 `1 + 0.13` 并保留四位小数。

## 冻结的成功输出

```json
{
  "schemaVersion": "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
  "poNo": "POJS2607170001",
  "orderNumber": "ERP 返回的订单号",
  "supplierCode": "02556",
  "supplierName": "供应商名称",
  "lineCount": 3,
  "lines": [
    {
      "poNo": "POJS2607170001",
      "lineNumber": "10",
      "customerItemNumber": "1B.30040.020262"
    }
  ]
}
```

成功输出不得出现 `draft`、`orderDetail`、`erpPayload`、`erpResponse`、`draftOnly`、`transmitted`、Access Token、Authorization Header 或任何凭据字段。

## ERP 结果和幂等边界

只有 HTTP 2xx、顶层 `code=2000`、`success=true`、非空 `rows`、所有行 `processStatusCode=COMPLETE`、且所有成功行给出同一个非空 ERP 订单号时才成功。

任一 ERP 行为 `ERROR` 时返回 `ERP_ORDER_IMPORT_ROW_FAILED`。提交后的超时、断连、取消、限流、服务端错误、矛盾响应或无法确认 ERP 订单号时进入 `WAITING_HUMAN / ERP_ORDER_IMPORT_OUTCOME_UNKNOWN`，禁止自动再次提交。

XLSX 不提供稳定源记录 ID，因此 Flow 仍没有可靠 ERP 幂等键。生产启用前需要 ERP 幂等/查询契约或 Engine 的提交后重试屏障。

## Artifact 和凭据限制

下载文件和 `supplier-portal-erp-draft-prepared` 截图继续通过 `ctx.artifacts` 登记。截图前会等待下载确认弹窗消失、详情和明细可见、加载遮罩消失、字体和图片完成、布局连续稳定，并额外等待约 300ms。

根据已批准的私有包例外，ERP OAuth 凭据位于受控私有 Flow 包中。不得把源码或 ZIP 提交到公开仓库、公开制品库或不受控日志；不得输出凭据、Token、Authorization Header、OAuth 查询参数或原始认证响应。