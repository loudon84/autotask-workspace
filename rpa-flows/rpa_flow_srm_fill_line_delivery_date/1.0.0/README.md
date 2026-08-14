# 按行填写预计交货日期 Flow（rpa_flow_srm_fill_line_delivery_date 1.0.0）

## 用途

流程实例节点2「填写交货日期」的子任务 Flow：客服在 Client 页面为某一行填写预计交货日期后，
由本 Flow 登录客户 SRM 门户，进入订单详情页，只填写并保存这一行。

与任务二（`rpa_flow_supplier_portal_update_delivery_dates`）的区别：

- 输入为单行（`po_no` + `line_number` + `expected_delivery_date`），不要求整单行齐
- 优先点击行级保存按钮 `pend-order-detail-save-line-{line}`，不存在时回退整单保存按钮
- 不发起签章；保存后刷新页面复核值已持久化

## 输入

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `po_no` | 是 | 客户采购订单号 |
| `line_number` | 是 | 订单行号 |
| `expected_delivery_date` | 是 | 预计交货日期（YYYY-MM-DD） |

## 输出

```json
{
  "schemaVersion": "SRM_FILL_LINE_DATE_OUTPUT_V1",
  "poNo": "POJS2607130002",
  "lineNumber": "10",
  "expectedDeliveryDate": "2026-08-20",
  "saved": true,
  "idempotent": false
}
```

幂等：门户该行已是目标值时直接成功，`idempotent=true`；订单已回签时返回业务错误 `ORDER_ALREADY_SIGNED`。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `FLOW_INPUT_INVALID` | 输入缺失或格式错误 |
| `BUSINESS_NOT_FOUND` | 订单不存在 |
| `ORDER_LINE_NOT_FOUND` / `ORDER_LINE_DATA_AMBIGUOUS` | 目标行不存在或重复 |
| `ORDER_ALREADY_SIGNED` | 订单已回签，不可再编辑 |
| `ORDER_NOT_EDITABLE` | 日期字段不可编辑或无可用保存按钮 |
| `ORDER_LINE_SAVE_REJECTED` | 门户拒绝保存 |
| `ORDER_LINE_SAVE_OUTCOME_UNKNOWN` / `ORDER_LINE_SAVE_UNCONFIRMED` | 保存结果需人工确认 |
