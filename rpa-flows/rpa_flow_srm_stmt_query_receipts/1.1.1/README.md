# SRM 收货列表查询（rpa_flow_srm_stmt_query_receipts 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示门户继续用 `1.0.3`（源码树对应 `1.0.0`）。

查询 SRM 收货列表（对账状态=未提交 + 入库确认时间范围），返回规范化 `rows[]`。

**禁止**点击「生成对账单」或任何写操作。

## 1.1.0 变更

- 正式站专用：去掉全部 `data-rpa`。
- 收货路由改为 `#/order/receivingList`（不再用演示站 `#/supplier/receivings`）。
- 采集脚本取页面上行数最多的 `.el-table`，不查 `data-rpa='receiving-list-page'`。

## Input

- `dateStart` / `dateEnd`：入库确认时间起止（`YYYY-MM-DD`）

## Output

```json
{
  "schemaVersion": "SRM_STMT_RECEIPTS_OUTPUT_V1",
  "totalRows": 1,
  "rows": [{ "receiptNo": "WR...", "lineNo": "10", "taxIncludedAmount": "..." }]
}
```
