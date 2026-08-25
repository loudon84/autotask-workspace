# 供应商门户双方签章合同上传 Flow

## 基本信息

- Flow ID：`rpa_flow_supplier_portal_upload_order_attachment`
- 版本：`1.1.0`
- Workflow code：`srm_upload_order_attachment`
- Portal type：`MOCK_SRM`
- 入口：`flow.py:run`

本 Flow 登录供应商门户，打开**已回签**订单详情，点击「**查看签章**」下载**双方签章合同**（PDF），再上传到 SDMS 附件系统。

**禁止**使用「下载订单」拿到的订单 XLSX / XML 作为本节点附件（那是建单用的订单文件，不是签章合同）。

## 输入契约

```json
{
  "po_no": "POJS2607130002"
}
```

附件展示名：`签章合同{po_no}`。测试包固定 `flag=sdms`、`username=S01`。

## 门户策略

1. 必须确认回复状态为「已回签」。
2. 必须存在「查看签章」按钮（`order-detail-view-sign-btn`）。
3. 点击「查看签章」直接触发合同下载（演示门户返回 PDF）。
4. 若下载到 `.xlsx/.xls/.xml` 或 ZIP/XLSX 魔数，报 `SIGNED_CONTRACT_WRONG_FILE`。

## 写操作与幂等

与 1.0.x 相同：查询幂等、同名不同内容转人工、上传最多一次、上传后查询确认。

## 成功输出

Schema 仍为 `ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1`；`sourceFileName` 为合同原文件名（如 `PURCHASE_ORDER.pdf`），`attachmentName` 为 `签章合同{po_no}`。
