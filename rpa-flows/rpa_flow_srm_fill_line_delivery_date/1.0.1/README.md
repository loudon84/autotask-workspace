# SRM 按行填写交货日期 Flow（rpa_flow_srm_fill_line_delivery_date 1.0.1）

## 用途

登录客户 SRM 门户，打开待签章订单详情，对**单行**填写预计交货日期并点击该行「保存」。
成功以门户保存成功提示为准；**不再 reload 校验 SRM 是否落库**。

业务约定：AutoTask 流程实例行上的 `expected_delivery_date` 是交期真相来源；演示门户可能只有成功提示、不写库。节点 2 与节点 3（签章）仍分离，填交期不等于签章。

## 1.0.1 变更

- 删除 `verify_persisted`（不再因刷新后日期为空报 `ORDER_LINE_SAVE_UNCONFIRMED`）
- 成功输出日期取自任务输入（与 AutoTask 已存值一致）
- 固定列表格选择器优先 `.el-table__fixed-right`，并用 `.first` 避免三份克隆导致的 strict mode

## 输入

```json
{
  "po_no": "POJS2607180002",
  "line_number": "10",
  "expected_delivery_date": "2026-09-15"
}
```

## 输出

```json
{
  "schemaVersion": "SRM_FILL_LINE_DATE_OUTPUT_V1",
  "poNo": "POJS2607180002",
  "lineNumber": "10",
  "expectedDeliveryDate": "2026-09-15",
  "saved": true,
  "idempotent": false,
  "portalPersisted": false
}
```

`portalPersisted=false` 表示本 Flow 不以 SRM 落库作为成功条件。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `FLOW_INPUT_INVALID` | 输入非法 |
| `ORDER_ALREADY_SIGNED` | 已回签不可改 |
| `ORDER_LINE_NOT_FOUND` / `ORDER_LINES_NOT_FOUND` | 行不可见 |
| `ORDER_NOT_EDITABLE` | 日期框或保存按钮不可用 |
| `ORDER_DATE_FILL_FAILED` | 填写后输入框未保留值 |
| `ORDER_LINE_SAVE_REJECTED` / `ORDER_LINE_SAVE_FAILED` / `ORDER_LINE_SAVE_OUTCOME_UNKNOWN` | 保存动作失败或无结果提示 |
