# SRM 扫单 Flow（rpa_flow_srm_scan_pending_orders 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。选择器基于登录占位符、表头文字和 `.el-table`。**不能绑演示门户**（`http://192.168.102.247:3000`）。演示门户继续用 `1.0.1`。

## 用途

登录客户 SRM 门户，遍历订单列表全部分页，采集「回复状态 = 待签章」的采购订单。只读，不执行写操作。正式站当前待签章常为 0，空列表仍 SUCCESS。

## 1.1.0 变更

- 正式站专用：去掉全部 `data-rpa`。
- 订单列表路由改为 `#/order/list`（不再用演示站 `#/supplier/orders`）。
- 登录成功判据改为顶栏「订单」菜单；验证码为 data-URL PNG 时走 `HUMAN_VERIFICATION_REQUIRED`。

## 输入

无。门户地址与凭据由 Engine 注入。

## 输出

与 1.0.1 相同：`SRM_PENDING_ORDERS_OUTPUT_V1`，`orders[]` 仅含待签章。
