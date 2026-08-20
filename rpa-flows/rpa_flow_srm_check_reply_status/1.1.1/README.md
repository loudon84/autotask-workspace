# SRM 回签状态只读探测（rpa_flow_srm_check_reply_status 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。按订单编号搜列表、点该行「详情」、读 `.el-tag` 文案。**不能绑演示门户**。演示门户继续用 `1.0.0`。

供回签轮询调度器使用：登录 → 打开订单详情 → 读取回复状态标签 → 输出 `replyStatus`。

**禁止**点击签章或任何写操作。

## 1.1.0 变更

- 正式站专用：去掉全部 `data-rpa`。
- 订单列表路由 `#/order/list`。
- 按行文本匹配 PO，点击「详情/查看」；回复状态从可见 `el-tag` 中匹配 `已回签/待回签/待签章`。

## 输入

```json
{ "po_no": "POJS2607170008" }
```

## 成功输出

```json
{
  "schemaVersion": "SRM_CHECK_REPLY_STATUS_OUTPUT_V1",
  "poNo": "POJS2607170008",
  "replyStatus": "已回签"
}
```

## Workflow

- Flow ID：`rpa_flow_srm_check_reply_status`
- Template code：`srm_check_reply_status`
