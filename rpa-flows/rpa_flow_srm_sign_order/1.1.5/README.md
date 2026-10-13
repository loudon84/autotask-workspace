# SRM 签章 Flow（正式门户 rpa_flow_srm_sign_order 1.1.5）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。演示站继续用 `1.0.3`。

相对 1.1.4：开详情后 DOM 仍保留「订单列表」页签；其右侧固定列是「详情」链接。1.1.4 误用该 fixed-right，MARK 报 `date_input_missing`，引擎重试表现为列表⇄详情来回切。1.1.5 把行号/交期定位限制在**订单详情**页签内：优先右侧固定区带日期框的第一列（供方交期），否则回退到详情主表该行的日期框。等待详情时最多点一次「订单详情」页签。

交期已由 AutoTask 本地保存。本包登录正式 SRM → 打开订单详情 → 把 `order_lines` 填入「供方交期」→ 点「签章」。正式站无单独「保存交期」；交期与签章一并提交。

## dryRun

Binding `dryRun: true`：仍登录、开单、填供方交期、确认「签章」可见可点并截图，**不 click 签章**。上线去掉 `dryRun` 才真点。

禁止在 `dryRun: true` 时点击门户「签章」。

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "dryRun": true
}
```

## 输入

```json
{
  "po_no": "POJS2610120010",
  "order_lines": [
    { "line_number": "10", "expected_delivery_date": "2026-11-28" }
  ]
}
```

Task `request_sign` 始终传 `order_lines`。
