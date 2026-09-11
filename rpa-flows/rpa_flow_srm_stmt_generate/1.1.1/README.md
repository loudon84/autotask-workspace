# SRM 生成对账单（rpa_flow_srm_stmt_generate 1.1.1）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示继续用 `1.0.7`。

相对 1.1.0：查询后点**一次表头全选**（SRM 会勾上本次查询全部行，不必翻页、不必改每页条数），再核对分页「共 N 条」与 Client `lines` 数量。对不上就失败，不点生成。

演练与上线同一包。Binding `dryRun: true` 时：全选并核对数量、等到「生成对账单」可见且可点、截图、**不 click**。上线把 `dryRun` 改为 `false` 或删除后才会真点。

## 演练红线

禁止在 `dryRun: true` 时点击门户「生成对账单」。缺按钮或按钮禁用视为失败（演练要真找到按钮）。

## Input

- `dateStart` / `dateEnd`：`YYYY-MM-DD`
- `lines[]`：`receiptNo` + `lineNo`（可带 `orderNo`）；**数量**须等于 SRM 本次查询总条数
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
