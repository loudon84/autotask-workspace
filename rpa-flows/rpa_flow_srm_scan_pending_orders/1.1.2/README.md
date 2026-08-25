# SRM 扫单 Flow（rpa_flow_srm_scan_pending_orders 1.1.2）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。**不能绑演示门户**（`http://192.168.102.247:3000`）。演示门户继续用 `1.0.2`。

## 用途

登录客户 SRM 门户，在订单列表：

1. 回复状态选「待签章」，不加其它条件，点查询。
2. 点导出，用 Excel 建后续客户订单任务。
3. 待签章无数据时（演练）：重置条件，按订单编号 `POJS2607170008` 查询再导出，把该单当成待签章扫入。不在 SRM 改状态。

只读，不点保存/签章/提交。

## 1.1.2 变更

- 数据来源从「翻页读表格」改为「查询后导出 Excel」。
- 演练空待签章只改搜索条件，不在 Task 里造假订单。

## 1.1.1 变更

- 正式站验证码用 Engine `ddddocr` 自动识别。

## 输入

可选 `assumedPendingPo`。默认 `POJS2607170008`；空字符串关闭演练回退。

## 输出

`SRM_PENDING_ORDERS_OUTPUT_V1`。`orders[]` 供 Task 创建客户订单。演练回退时带 `drill.assumedPending=true`。
