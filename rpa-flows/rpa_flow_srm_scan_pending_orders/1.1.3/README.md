# SRM 扫单 Flow（rpa_flow_srm_scan_pending_orders 1.1.3）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。**不能绑演示门户**（`http://192.168.102.247:3000`）。演示门户继续用 `1.0.2`。

## 用途

登录客户 SRM 门户，按 Binding `config.searches` 依次：填条件 → 查询 → 导出 Excel。用 Excel 建后续客户订单。

只读，不点保存/签章/提交。

## 1.1.3 变更

- **不再默认** `POJS2607170008`。样例单号只来自 Binding `searches`。
- 没有 `searches`、或只有待签章且为空：空列表成功，不再扫样例单。
- 换演练单号：改 Binding 第二条 `poNo`。上线：删掉第二条。

## Binding

演练：

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "searches": [
    { "replyStatus": "待签章" },
    { "poNo": "POJS2607170008", "treatAsPending": true }
  ]
}
```

上线只留第一条。`treatAsPending` 不得进生产。

Task 必须把 Binding `searches` 放进租约 `config`（与 `dryRun` 同路）。改 Binding 后需重启唯一 Task 4520 和 Engine 4610。

## 输出

`SRM_PENDING_ORDERS_OUTPUT_V1`。`treatAsPending` 命中时带 `drill.assumedPending=true`。
