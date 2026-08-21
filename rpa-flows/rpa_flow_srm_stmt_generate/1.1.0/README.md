# SRM 生成对账单（rpa_flow_srm_stmt_generate 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示继续用 `1.0.7`。

演练与上线同一包。Binding `dryRun: true` 时：打开收货列表、按勾选行点 checkbox、等到「生成对账单」可见且可点、截图、**不 click**。上线把 `dryRun` 改为 `false` 或删除后才会真点。

## 演练红线

禁止在 `dryRun: true` 时点击门户「生成对账单」。缺按钮或按钮禁用视为失败（演练要真找到按钮）。

## Input

- `dateStart` / `dateEnd`：`YYYY-MM-DD`
- `lines[]`：`receiptNo` + `lineNo`（可带 `orderNo`）
- `localAmount`：可选

## Output

```json
{
  "schemaVersion": "SRM_STMT_GENERATE_OUTPUT_V1",
  "committed": false,
  "dryRun": true,
  "blockedAction": "generate_statement",
  "generateButtonFound": true,
  "checkAmount": "12.50",
  "selectedLineCount": 3
}
```
