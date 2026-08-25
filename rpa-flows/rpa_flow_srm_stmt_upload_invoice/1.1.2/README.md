# SRM 扫描发票（rpa_flow_srm_stmt_upload_invoice 1.1.2）

> **适用门户：正式门户**（`https://supplier.tiandy.com`，无 `data-rpa`）。**不能绑演示门户**。演示继续用 `1.0.6`。

相对 1.1.1：读发票号/总额的 JS 不再用非法 CSS `:visible`；选文件后**必须点弹窗「确定」**才开始识别；重试时若还停在应付页，先离开再进列表。
