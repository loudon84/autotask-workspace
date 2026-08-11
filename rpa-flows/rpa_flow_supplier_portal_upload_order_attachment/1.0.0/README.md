# 供应商门户订单附件上传 Flow

## 基本信息

- Flow ID：`rpa_flow_supplier_portal_upload_order_attachment`
- 版本：`1.0.0`
- Workflow code：`srm_upload_order_attachment`
- Portal type：`MOCK_SRM`
- 入口：`flow.py:run`

本 Flow 登录供应商门户，按采购订单号打开订单详情，确认回复状态为“已回签”，点击“下载订单”并将门户下载文件保存为 AutoTask Artifact。随后查询附件系统；没有相同文件时以 `multipart/form-data` 上传，并再次查询确认上传记录。

## 输入契约

```json
{
  "po_no": "POJS2607130002"
}
```

`po_no` 同时作为附件接口的 `order_number`。测试包固定使用 `flag=sdms`、`username=S01`，附件展示名为 `采购订单{po_no}`。生产地址、正式 `flag=SDMS` 或上传人工号变化时必须发布新 Flow 版本，不能覆盖本版本。

## 写操作和幂等边界

1. 必须先确认订单为“已回签”，否则不下载、不上传。
2. 下载按钮和确认按钮各点击一次；文件必须非空、文件名安全且不超过 200 MiB。
3. 外部上传前先保存下载 Artifact，Artifact 大小必须与本地下载字节一致。
4. 查询接口返回相同 `flag`、附件展示名、源文件名和大小时直接幂等成功，不再 POST。
5. 同展示名或同源文件名但内容大小不同，返回 `WAITING_HUMAN / ATTACHMENT_DUPLICATE_CONFLICT`。
6. 其他附件不阻止本文件上传；上传 POST 最多调用一次。
7. 上传超时、取消、408/429/5xx、响应不明确或上传后查询无法确认时进入 `WAITING_HUMAN`，不得自动再次 POST。
8. 上传成功后查询最多五次；必须找到相同附件 ID 和文件身份后才返回成功。

## 成功输出

```json
{
  "schemaVersion": "ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1",
  "poNo": "POJS2607130002",
  "attachmentOrderNumber": "POJS2607130002",
  "attachmentId": "1",
  "attachmentName": "采购订单POJS2607130002",
  "sourceFileName": "order.xlsx",
  "size": 4169,
  "uploader": "S01",
  "uploaded": true,
  "idempotent": false
}
```

幂等命中时 `uploaded=false`、`idempotent=true`。输出和日志不包含附件系统的 `path`、完整响应或门户凭据。

## Task 自动后继契约

任务 2 Flow 的成功输出 Schema 为 `ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1`。Task 服务应使用 `ORDER_ATTACHMENT_UPLOAD_V1` 映射器校验 `signed=true`、`replyStatus=已回签`，把 `poNo` 映射为任务 3 的 `po_no`，创建同 Portal、精确 Flow 版本的任务 3 并立即排队。该调度能力属于 Task 服务，不在本 Flow 包内实现。

## 证据和限制

- 保存 `supplier-portal-order-attachment-before-download` 截图。
- 下载文件必须通过 `ctx.artifacts.save_download` 登记。
- Flow 不自行启动浏览器、不连接数据库、不修改 Task 状态。
- 附件系统当前文档未定义鉴权，Flow 不发送 Authorization 头。