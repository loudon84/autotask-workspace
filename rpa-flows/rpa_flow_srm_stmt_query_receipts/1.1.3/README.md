# SRM 收货列表查询（rpa_flow_srm_stmt_query_receipts 1.1.3）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示门户继续用 `1.0.x`。

查询 SRM 收货列表，返回规范化 `rows[]`，并把导出的 Excel 存为 Artifact。

**禁止**点击「生成对账单」或任何写操作。

## 1.1.3 变更

- 起止时间写死为开始 `00:00:00`、结束 `23:59:59`。1.1.2 点时间框会弹出时间面板，下标错位后两端都变成 `23:59:59`，当天没有数据。
- 日历只负责选日期；四个表头输入用原生 value setter 写入，不 click 时间框。确定后回读关闭态输入，开始必须带 `00:00:00`。

## 1.1.2 变更

- 入库确认时间按正式站 Element UI 范围面板操作：点开「入库确认时间」→ 日历点起止日 → 点面板「确定」。Client 仍只传 `YYYY-MM-DD`。
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
