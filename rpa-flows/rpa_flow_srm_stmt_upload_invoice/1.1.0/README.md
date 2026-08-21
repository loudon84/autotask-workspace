# SRM 扫描发票（rpa_flow_srm_stmt_upload_invoice 1.1.0）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。**不能绑演示门户**。演示继续用 `1.0.6`。

第一次扫描：把发票号/发票总额回写到 Client，供客服核对。不点门户「提交审核」。

提交审核走 `rpa_flow_srm_stmt_submit_review`，会再扫一次并与这次结果比对。
