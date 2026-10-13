# SRM 签章 Flow（正式门户 rpa_flow_srm_sign_order 1.1.4）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。演示站继续用 `1.0.3`。

相对 1.1.3：详情是 table 行；**供方交期 = 右侧固定列区的第一列**（其后为欠交数量、操作）。多行按「订单行号 → 主表行下标 → `fixed-body-wrapper` 同行第一列日期框」对齐。禁止页面级「第一个日期框」回退。逐行填写回读，全部填完再整表复核。

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
