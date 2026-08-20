# 供应商门户双方签章合同上传 Flow

## 基本信息

- Flow ID：`rpa_flow_supplier_portal_upload_order_attachment`
- 版本：`1.2.3`
- Workflow code：`srm_upload_order_attachment`
- Portal type：`MOCK_SRM`
- 入口：`flow.py:run`

本 Flow 登录供应商门户，打开**已回签**订单详情，点击「**查看签章**」下载**双方签章合同**（PDF），再上传到 SDMS 销售订单附件接口。

**禁止**使用「下载订单」拿到的订单 XLSX / XML 作为本节点附件。

相对 1.2.2：ERP / 文档上传基址和 OAuth 客户端从租约 `ctx.config` / `ctx.credentials` 读取，源码不再写死测试环境地址和密钥。

相对 1.2.1：`username` 改为 Task 传入的 **Auth 登录账号**（SDMS 工号），不再写死测试工号。

## 输入契约

```json
{
  "po_no": "POJS2607130002",
  "username": "SMC-SZ-HR15563"
}
```

`username` 必须是当前 AutoTask Auth 登录账号。`filename` 为客户订单号 `po_no`。

## SDMS 上传

| 项 | 值 |
| --- | --- |
| Token | 与建 SDMS 销售订单相同：`POST {host}/core/oauth/token`，`grant_type=client_credentials` |
| 上传 | `POST {host}/core/api/srm/so/uploadAttachment`，Header `Authorization: bearer {token}` |
| `flag` | `SDMS_SO1`（固定） |
| `custPoNumber` | 客户订单号 `po_no` |
| `username` | Auth 登录账号（SDMS 工号） |
| `filename` | 客户订单号 `po_no` |
| `file` | 双方签章合同 |
| `uploadUrl` | `http://api.doc.uat.smart-core.com.hk/upload` |

新接口未提供附件列表查询，因此 **不再做上传前幂等查询 / 上传后回查**。Token、Authorization、OAuth 查询串不记日志、不进 Artifact。

## 门户策略

1. 必须确认回复状态为「已回签」。
2. 必须存在「查看签章」按钮。
3. 点击「查看签章」直接触发合同下载（演示门户返回 PDF）。
4. 若下载到 `.xlsx/.xls/.xml` 或 ZIP/XLSX 魔数，报 `SIGNED_CONTRACT_WRONG_FILE`。

## 成功输出

Schema 仍为 `ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1`；增加 `custPoNumber`。
