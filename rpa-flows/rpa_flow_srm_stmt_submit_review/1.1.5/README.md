# SRM 对账单提交审核（rpa_flow_srm_stmt_submit_review 1.1.5）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。对账列表 `#/reconciliation/reconciliationStatement`。**不能绑演示门户**。演示继续用 `1.0.7`。

相对 1.1.4：dryRun 写闸改到**扫描完成之后**才安装，避免拦截正式站发票上传（URL 往往不含 `/upload`）；点「确定」失败时改走 DOM click；进列表前先关掉残留弹窗。

客服先在 Client 扫描并核对发票号/总额，再点「提交审核」。本包再用同一批文件扫第二次；**与页面已核对结果不一致则失败，不点提交**。

Binding `dryRun: true`：第二次扫描通过后，对「提交审核」做 Playwright **trial click**（可见、可用、不被挡住；不真点）。上线去掉 `dryRun` 才真点。

## 演练红线

禁止在 `dryRun: true` 时点击门户「提交审核」。trial click 不算点击。
