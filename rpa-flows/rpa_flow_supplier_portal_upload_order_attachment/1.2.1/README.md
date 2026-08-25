# 供应商门户双方签章合同上传 Flow

## 基本信息

- Flow ID：`rpa_flow_supplier_portal_upload_order_attachment`
- 版本：`1.2.1`
- Workflow code：`srm_upload_order_attachment`
- Portal type：`MOCK_SRM`
- 入口：`flow.py:run`

本 Flow 登录供应商门户，打开**已回签**订单详情，点击「**查看签章**」下载**双方签章合同**（PDF），再上传到 SDMS 销售订单附件接口。

**禁止**使用「下载订单」拿到的订单 XLSX / XML 作为本节点附件。

相对 1.2.0：按 Postman 补上必填 `uploadUrl`（文档服务 `/upload` 地址），`filename` 用客户订单号，`username` 用 SDMS 工号；拒绝时回传接口 `message`。

## 输入契约

```json
{
  "po_no": "POJS2607130002"
}
```

附件展示名：客户订单号 `po_no`。测试包固定 `username=SMC-SZ-HR15563`。

## SDMS 上传

| 项 | 值 |
| --- | --- |
| Token | 与建 SDMS 销售订单相同：`POST {host}/core/oauth/token`，`grant_type=client_credentials` |
| 上传 | `POST {host}/core/api/srm/so/uploadAttachment`，Header `Authorization: bearer {token}` |
| `flag` | `SDMS_SO1`（固定） |
| `custPoNumber` | 客户订单号 `po_no` |
| `username` | `SMC-SZ-HR15563` |
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
