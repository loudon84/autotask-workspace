# SRM 对账单提交审核（rpa_flow_srm_stmt_submit_review 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。对账列表 `#/reconciliation/reconciliationStatement`。**不能绑演示门户**。演示继续用 `1.0.7`。

演练与上线同一包。Client 仍点「提交审核」（选发票后一次 RPA）。Binding `dryRun: true` 时：按对账日期+金额找到未对账行 → 进收货应付 → **真扫描发票** → 等到「提交审核」可见且可点、截图、**不 click**。上线把 `dryRun` 改为 `false` 或删除后才会真点门户提交。

## 演练红线

禁止在 `dryRun: true` 时点击门户「提交审核」。缺按钮或按钮禁用视为失败（演练要真找到按钮）。扫描发票允许真做。

不要单独绑 `rpa_flow_srm_stmt_upload_invoice`。生产也是一次 RPA 完成扫描+提交。

## Input

- `checkDate` / `checkAmount`：与本地 `statement_bills`、门户未对账行匹配键相同
- `filePaths[]`：本机发票路径（png/jpg/jpeg/pdf/ofd，最多 10 个）

## Output（演练）

```json
{
  "schemaVersion": "SRM_STMT_SUBMIT_REVIEW_OUTPUT_V1",
  "committed": false,
  "dryRun": true,
  "blockedAction": "submit_review",
  "submitButtonFound": true,
  "invoiceNo": "...",
  "invoiceAmount": "..."
}
```
