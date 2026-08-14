# SRM 扫单 Flow（rpa_flow_srm_scan_pending_orders 1.0.1）

## 用途

登录客户 SRM 门户，遍历订单列表全部分页，采集「回复状态 = 待签章」的采购订单，
输出给 Task 服务用于幂等创建流程实例（process_instances）。该 Flow 只读，不执行任何写操作。

## 1.0.1 变更

- 修正列表表头：门户真实列名为「订单编号」（1.0.0 误用「采购单号」导致 `totalRows=0`）
- 表头匹配支持别名：`订单编号/采购单号`、`总金额(元)/总金额`、`交货状态/发货状态`、`供应商单位/主体`
- 必填表头缺失时返回业务错误，避免静默空结果
- 多 `.el-table` 时优先选择行数最多的主表

## 输入

无（inputSchema 为空）。门户地址与凭据由 Engine 注入（`ctx.portal_url` / `ctx.credentials`）。

## 输出

```json
{
  "schemaVersion": "SRM_PENDING_ORDERS_OUTPUT_V1",
  "portalUrl": "http://...",
  "totalRows": 16,
  "orders": [
    {
      "poNo": "POJS2607130002",
      "orderDate": "2026-07-13",
      "orderType": "普通订单",
      "totalAmount": "84,208,626.83",
      "replyStatus": "待签章",
      "deliveryStatus": "未发货",
      "supplierName": "..."
    }
  ]
}
```

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `PORTAL_URL_MISSING` | 未注入门户地址 |
| `SRM_CREDENTIALS_MISSING` | 凭据不可用 |
| `HUMAN_VERIFICATION_REQUIRED` | 验证码需人工 |
| `SRM_LOGIN_FAILED` / `SRM_LOGIN_TIMEOUT` / `SRM_LOGIN_PAGE_UNAVAILABLE` | 登录失败 |
| `ORDER_LIST_UNAVAILABLE` | 列表页无法打开、读取或缺少订单编号/回复状态表头 |

## 选择器依赖

- 登录页：`login-*`（与既有 Flow 一致）
- 列表页：`order-list-page`、`.el-table`、`.el-pagination .btn-next`
- 列表表头必须包含：订单编号（或采购单号）、回复状态（其余列缺失时输出空字符串）
