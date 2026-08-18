# SRM Statement Query Receipts 1.0.0

查询 SRM 收货列表（对账状态=未提交 + 入库确认时间范围），返回规范化 `rows[]`。

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

## Notes
- 选择器使用 `data-rpa='receipt-list-page'`；mock_srm 尚未内置对账页签时，Flow 会返回 `SRM_STMT_RECEIPT_PAGE_MISSING`，需补 mock 或对接真实 SRM。
