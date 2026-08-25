# SRM 收货列表查询（rpa_flow_srm_stmt_query_receipts 1.1.2）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示门户继续用 `1.0.x`。

查询 SRM 收货列表，返回规范化 `rows[]`，并把导出的 Excel 存为 Artifact。

**禁止**点击「生成对账单」或任何写操作。

## 1.1.2 变更

- 入库确认时间按正式站 Element UI 范围面板操作：点开「入库确认时间」→ 日历点起止日 → 时间保持 `00:00:00` / `23:59:59` → 点面板「确定」。Client 仍只传 `YYYY-MM-DD`。
- 查询前在表单里选 **对账状态 = 未提交**（不是导出后再筛）。
- 点「查询」后点「导出」，解析 xlsx 给填单页；不再翻页刮 HTML。

## Input

- `dateStart` / `dateEnd`：入库确认日期起止（`YYYY-MM-DD`）

## Output

```json
{
  "schemaVersion": "SRM_STMT_RECEIPTS_OUTPUT_V1",
  "totalRows": 1,
  "source": "xlsx",
  "sourceFilter": "对账状态=未提交",
  "rows": [{ "receiptNo": "WR...", "lineNo": "10", "taxIncludedAmount": "..." }]
}
```
