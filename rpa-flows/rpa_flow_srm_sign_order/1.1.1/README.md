# SRM 签章 Flow（正式门户 rpa_flow_srm_sign_order 1.1.1）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。演示站继续用 `1.0.3`。

相对 1.1.0：列表「详情」在右侧固定列，改用与 prepare 相同的可见点击逻辑，并等 hash/签章按钮确认进详情。

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
