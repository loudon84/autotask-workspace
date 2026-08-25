# SRM 回签状态只读探测（rpa_flow_srm_check_reply_status 1.0.1）

## 1.0.1 变更

- 登录验证码改为本机 `ddddocr` 读图，不再用文件名对照。
- 最多 3 次；失败抛可重试错误，不停成待人工。
- **适用门户：演示门户**（`http://192.168.102.247:3000`）。不能绑正式门户。

供 v2.02 回签轮询调度器使用：登录 → 打开订单详情 → 读取回复状态标签 → 输出 `replyStatus`。

**禁止**点击签章或任何写操作。

## 输入

```json
{ "po_no": "POJS2607180002" }
```

## 成功输出

```json
{
  "schemaVersion": "SRM_CHECK_REPLY_STATUS_OUTPUT_V1",
  "poNo": "POJS2607180002",
  "replyStatus": "已回签"
}
```

`replyStatus` 常见值：`待签章` / `待回签` / `已回签`（以门户标签文案为准）。

## Workflow

- Flow ID：`rpa_flow_srm_check_reply_status`
- Template code：`srm_check_reply_status`
