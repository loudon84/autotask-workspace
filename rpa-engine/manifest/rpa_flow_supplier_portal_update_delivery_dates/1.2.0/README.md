# 供应商门户预计交货日期直签 Flow

## 基本信息

- Flow ID：`rpa_flow_supplier_portal_update_delivery_dates`
- 版本：`1.2.0`
- Workflow code：`srm_update_expected_delivery_dates`
- Portal type：`MOCK_SRM`
- 入口：`flow.py:run`

本 Flow 使用 Engine 托管的 Playwright 页面，登录供应商门户，按订单编号搜索订单并点击搜索结果中的“详情”。门户会根据订单状态进入待签章详情或正式详情；可编辑订单逐行填写预计交货日期后直接签章，不再单独点击顶部或逐行“保存”。已回签订单只执行幂等核对。

## 输入契约

```json
{
  "po_no": "POJS2607130002",
  "order_lines": [
    {
      "line_number": "10",
      "material_number": "1B.30040.020262",
      "expected_delivery_date": "2026-08-10"
    },
    {
      "line_number": "20",
      "material_number": "1B.30040.020262",
      "expected_delivery_date": "2026-08-12"
    }
  ]
}
```

- `po_no` 必填。
- `order_lines` 必须是非空数组，并完整覆盖门户中的全部订单行。
- `line_number` 必填且在输入中唯一，是订单行的匹配主键。
- `material_number` 必填，用于防止行号与料号错配；不同订单行允许使用相同料号。
- `expected_delivery_date` 必须是合法、规范的 `YYYY-MM-DD` 日期。
- 缺行、多行、重复行号或料号不一致都会在任何签章操作前失败。
- Flow 不硬编码订单行数；当前八行订单只有在输入完整覆盖八行且八行均通过校验时才会签章成功。

## 写操作边界

正常执行顺序固定为：

1. 读取门户全部订单行，并按行号、料号核对输入是否完整覆盖。
2. 填写全部预计交货日期并核验页面输入值。
3. 等待页面稳定，记录签章前截图。
4. 不点击顶部“保存”，也不点击逐行“保存”；只点击一次“签章”。
5. 签章结果明确成功后重载页面。
6. 验证回复状态为“已回签”、签章按钮不可执行，并重新读取门户全部订单行。
7. 逐行验证重载后的预计交货日期与输入完全一致；当前八行订单必须通过 8/8 行验证。
8. 等待页面稳定，记录签章后截图并返回成功。

签章点击后如遇超时、断连、取消或无法确认结果，Flow 进入 `WAITING_HUMAN / ORDER_SIGN_OUTCOME_UNKNOWN`，不会自动再次点击。签章成功消息明确但刷新后的状态、按钮或任一行日期无法确认时，返回 `WAITING_HUMAN / ORDER_SIGN_STATUS_UNCONFIRMED`。

## 已回签幂等策略

打开订单时若回复状态已经是“已回签”：

- 所有行的行号、料号和已保存日期与输入完全一致：不再填写或签章，直接返回成功。
- 任意一行日期不同：返回 `WAITING_HUMAN / ORDER_ALREADY_CONFIRMED_CONFLICT`，由人工确认。

非编辑状态下，Flow 仍会从只读表格读取行号、料号和预计交货日期。待签章详情使用 `pend-order-detail-*`，正式详情使用 `order-detail-*`；Flow 不硬编码详情路由。

如果正式详情页没有渲染预计交货日期，Flow 无法证明日期与输入一致，会保持 `WAITING_HUMAN / ORDER_ALREADY_CONFIRMED_CONFLICT`，不会再次签章。若回复状态本身无法读取，Flow 同样不会执行签章。

## 截图证据

正常直签闭环记录：

- `supplier-portal-delivery-dates-before-sign`：全部日期填妥、逐行核验且页面稳定，尚未签章。
- `supplier-portal-delivery-dates-signed`：签章后重载，完整显示“已回签”，且全部日期再次核验完成。

稳定门禁会等待加载遮罩消失、行数和日期渲染正确、可见图片加载完成、字体就绪以及布局连续两次保持一致，最后再等待约 300ms。失败现场截图立即执行，不等待稳定。

## Runtime 配置

- 门户地址来自 Task/Portal Binding 的 `config.portalUrl`，在 Flow 中使用 `ctx.portal_url`。
- 门户凭据由 Portal `credentialRef` 注入只读 `ctx.credentials`；Flow 同时兼容普通 `dict` 和 Engine 的 `MappingProxyType`。
- 包内不包含门户凭据、内部地址、浏览器启动代码或 CDP 连接代码。

## 成功输出契约

```json
{
  "schemaVersion": "ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1",
  "poNo": "POJS2607130002",
  "lineCount": 8,
  "saved": true,
  "signed": true,
  "replyStatus": "已回签",
  "lines": []
}
```

`schemaVersion` 用于 Task 服务在任务 2 成功后映射并自动排队任务 3。为保持下游契约兼容，`saved` 仍为 `true`，其含义是签章后刷新已证明全部日期持久化成功，不表示 Flow 点击过“保存”按钮。