# SRM 只签章 Flow（rpa_flow_srm_sign_order 1.0.1）

## TEMP E2E ONLY（联调后必须去掉）

演示门户「保存交期」不落库时，节点3签章前无法从 SRM 读到交期。
本版本支持输入：

```json
{
  "po_no": "POJS2607180002",
  "temp_e2e_backfill_dates": true,
  "order_lines": [
    {"line_number": "10", "expected_delivery_date": "2026-09-15"},
    {"line_number": "20", "expected_delivery_date": "2026-09-20"}
  ]
}
```

行为：打开详情后，把 AutoTask 交期填入页面输入框（不点保存），再点签章。
正式门户可持久化后：删除 Flow 回填逻辑，并删除 Task `request_sign` 中的 `temp_e2e_backfill_dates` / `order_lines` 传参。

## 正常路径（无 TEMP 字段）

仍要求门户页面上每行预计交货日期已填，否则 `ORDER_DATES_INCOMPLETE`。
