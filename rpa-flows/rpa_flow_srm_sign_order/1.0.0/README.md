# 只签章 Flow（rpa_flow_srm_sign_order 1.0.0）

## 用途

流程实例节点3「发起签章」的子任务 Flow：登录客户 SRM 门户，进入订单详情页，
复核所有行均已填写预计交货日期后，点击「签章」发起订单合同签章申请。

与任务二（`rpa_flow_supplier_portal_update_delivery_dates`）的区别：

- 不填写任何日期，只做签章前置复核 + 签章
- 签章后回复状态接受「待回签」或「已回签」（双方签章是线下过程，不在本 Flow 范围）

## 输入

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `po_no` | 是 | 客户采购订单号 |

## 输出

```json
{
  "schemaVersion": "SRM_SIGN_ORDER_OUTPUT_V1",
  "poNo": "POJS2607130002",
  "signed": true,
  "replyStatus": "待回签",
  "idempotent": false,
  "lineCount": 8
}
```

幂等：订单已是「待回签/已回签」时直接成功，`idempotent=true`。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `FLOW_INPUT_INVALID` | 订单号缺失或格式错误 |
| `BUSINESS_NOT_FOUND` | 订单不存在 |
| `ORDER_DATES_INCOMPLETE` | 存在未填写预计交货日期的行，禁止签章 |
| `ORDER_NOT_EDITABLE` | 签章按钮不可用 |
| `ORDER_SIGN_REJECTED` | 门户拒绝签章 |
| `ORDER_SIGN_OUTCOME_UNKNOWN` / `ORDER_SIGN_STATUS_UNCONFIRMED` | 签章结果需人工确认 |
