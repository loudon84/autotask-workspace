# SRM 对账单提交审核（rpa_flow_srm_stmt_submit_review 1.1.7）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。对账列表 `#/reconciliation/reconciliationStatement`。**不能绑演示门户**。演示继续用 `1.0.7`。

相对 1.1.6：修复「假 SUCCESS」。根因（2026-10-10 正式三次 SUCCESS 空跑、SRM 侧始终未对账/未上传）：点「提交审核」后只等泛化的 `.el-message--success`，而 1 秒前发票「上传成功」toast 还未消失（el-message 默认展示 3s），被误判为提交成功；同时输出里的 `checkStatus/invoiceStatus` 是硬编码的「已对账/审核中」，并非页面真实状态。1.1.7 改为：

1. 点提交前先等残留成功 toast 消失；
2. 提交成功的判定改为**路由跳回对账列表**（门户提交成功处理里的 `$router.push`）或点击后**新出现**的成功 toast；
3. 出现 `.el-message--warning`（门户前端校验拦截，如「请上传发票」、明细表 `rcvQty` 校验）抛 `SRM_STMT_SUBMIT_BLOCKED` 并带 toast 原文；错误 toast 抛 `SRM_STMT_SUBMIT_FAILED`；
4. 提交确认后回读对账列表该行的真实「对账状态 / 发票状态」写入输出（回读失败才兜底填预期值）。

依据：正式站前端 chunk 源码——`handleApprove` 无二次确认弹窗，成功即 `$message.success` + `$router.push` 回列表，校验失败只弹 warning toast、不发请求。

相对 1.1.5：修复「确定」点击超时 / `STMT_INVOICE_OCR_EMPTY`。根因：发票上传期间门户挂全屏「上传中，请稍候...」遮罩盖住「确定」，1.1.5 在上传完成前（固定等 400ms）就点「确定」，遮罩存续时 Playwright 命中测试必超时、DOM click 穿透后门户不响应，弹框不关、发票号回读为空。1.1.6 改为**先等上传完成**（成功 toast 或遮罩消失，上限 60s，失败 toast 直接报错）再点「确定」，点击前再兜底等一次遮罩消失。

相对 1.1.4：dryRun 写闸改到**扫描完成之后**才安装，避免拦截正式站发票上传（URL 往往不含 `/upload`）；点「确定」失败时改走 DOM click；进列表前先关掉残留弹窗。

客服先在 Client 扫描并核对发票号/总额，再点「提交审核」。本包再用同一批文件扫第二次；**与页面已核对结果不一致则失败，不点提交**。

Binding `dryRun: true`：第二次扫描通过后，对「提交审核」做 Playwright **trial click**（可见、可用、不被挡住；不真点）。上线去掉 `dryRun` 才真点。

## 演练红线

禁止在 `dryRun: true` 时点击门户「提交审核」。trial click 不算点击。
