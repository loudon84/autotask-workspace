# SRM 按行填写交货日期 Flow（rpa_flow_srm_fill_line_delivery_date 1.0.2）

## 1.0.2 变更

- 日期/保存控件改为先选 `.el-table__fixed-right`，避免 Playwright union+`.first` 点到 body 克隆导致 `ORDER_DATE_FILL_FAILED`
- 登录支持复用已登录会话（Runtime 重试同 context 时不再误报 `SRM_LOGIN_PAGE_UNAVAILABLE`）
- 填写改用 `type` + Enter，并回读 DOM value

## 成功判定（继承 1.0.1）

填写 → 点保存 → 成功提示即 SUCCESS；不以 SRM 是否落库为准，日期以任务输入（AutoTask）为准。
