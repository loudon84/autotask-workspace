# SRM 生成对账单（rpa_flow_srm_stmt_generate 1.1.3）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。收货页 `#/order/receivingList`。**不能绑演示门户**。演示继续用 `1.0.7`。

相对 1.1.2：查询后把每页改成 **100 条**，核对「共 N 条」等于填单 `lines` 数量，再点表头 checkbox（影刀 xpath：`//table//tr/th//span[contains(@class, "el-checkbox__inner")]`）。N≤100 不翻页；N>100 则下一页再点表头，直到没有下一页。不逐行勾、不读「已选择」。

演练与上线同一包。Binding `dryRun: true` 时：全选并核对数量、等到「生成对账单」可见且可点、截图、**不 click**。上线把 `dryRun` 改为 `false` 或删除后才会真点。

## 演练红线

禁止在 `dryRun: true` 时点击门户「生成对账单」。缺按钮或按钮禁用视为失败（演练要真找到按钮）。

## Input

- `dateStart` / `dateEnd`：`YYYY-MM-DD`
- `lines[]`：`receiptNo` + `lineNo`（可带 `orderNo`）；**数量**须等于查询「共 N 条」
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
