# AutoTask v3.02 业务需求：天地伟业对账单优化

| 项 | 内容 |
| --- | --- |
| 版本 | **v3.02** |
| 基线 | [v3.0 业务定稿](./AutoTask%20v3.0%20业务需求-天地伟业对账单.md)；体验与 SOP 继承 [v3.01](./AutoTask%20v3.01%20业务需求-天地伟业对账单SOP.md) |
| 状态 | 已确认（2026-08-18）；相对 v3.0/v3.01 的三处补丁，联调通过后即可做 |
| 原则 | 只写相对既有版本的增量；未列出的规则继续以 v3.0 / v3.01 为准 |
| 计划 | **不单独开 Cursor Plan**：三项都有现成蓝本（文案、客户订单 SDMS 链接、客户订单附件 HTTP），直接开发 |

---

## 0. 版本关系

```text
v3.0    天地伟业对账单业务定稿（生成 / 发票 / 提交 / 待生成草稿）
  └─ v3.01  SOP 体验（阶段、进度条、一次 RPA 扫描并提交）
       └─ v3.02  本文：详情用词、SDMS 对账单映射与链接、提交后把发票传到 SDMS
```

---

## 1. 问题

功能测试已基本通过。客服在详情页仍会碰到三处不一致：

1. 生成页勾选的是 **SRM 收货明细**（来源）；落库之后详情仍叫「收货明细」，像还在填单。
2. SDMS 校验接口已能返回对账单号 `check_num` 和主键 `check_head_id`，详情没有展示，也不能像客户订单那样打开 SDMS。
3. 发票只进了 SRM。业务还要把同一批发票挂到 **SDMS 对账单** 上，接口形态与客户订单「上传附件到 SDMS」相同，只是 `flag` / `order_number` 不同。

---

## 2. Changelog（相对 v3.0 / v3.01）

| # | 类型 | 主题 | 现行 | v3.02 |
| --- | --- | --- | --- | --- |
| O1 | 用词 | 详情明细区标题 | 详情叫「收货明细」 | 详情改称 **对账明细**。生成/填单页仍叫收货明细（来源） |
| O2 | 映射 | SDMS 对账单 | 只存 `check_head_id`，详情不展示 | 校验结果增加 `check_num`；详情展示 **SDMS对账单** = `check_num`，链接打开 SDMS 查看页 |
| O3 | 附件 | 发票去向 | 一次 RPA 只把发票扫进 SRM 并提交 | SRM 提交成功后，同一批本机发票再按附件接口传到 SDMS 对账单 |

---

## 3. O1 对账明细（文案）

| 页面 | 叫法 | 原因 |
| --- | --- | --- |
| 生成对账单（填单） | **收货明细** | 数据来自 SRM 未提交收货列表，是对账单的来源 |
| 对账单详情 | **对账明细** | 已经是这张对账单勾选进来的行，不再是「收货列表」 |

- 空态文案改为「暂无对账明细。生成时勾选的收货行会显示在这里。」
- 表头字段（收货单号、收货单行号等）保持附件 3，不改列名。
- 明细仍只存在流程实例 `summary.lines`，**不新增 `statement_bills` 列、不执行 DDL**。

v3.0 §3.3 中「对账单详情页的明细行」同步改称对账明细；生成页流程图仍用「收货明细」。

---

## 4. O2 客户对账单 ↔ SDMS 对账单

### 4.1 校验接口增量

SDMS 当月查询（现有 `view_doc_srm`）`data[]` 现含：

```json
[
  {
    "check_head_id": 36775,
    "check_num": "104DZ26080001",
    "check_amount": 1151309.12
  }
]
```

| 字段 | 含义 | 本地怎么用 |
| --- | --- | --- |
| `check_head_id` | SDMS 对账单主键（示例 `36775`） | 已有列 `statement_bills.sdms_check_head_id`；链接 `fdId` |
| `check_num` | SDMS 对账单号（示例 `104DZ26080001`） | **不新增列**；写入 `process_instances.summary.sdms_check_num`；详情 DTO `sdmsCheckNum` |
| `check_amount` | 对账金额 | 沿用 v3.0：与勾选汇总无容差比较 |

`check_num` 不是 SRM 对账单号。SRM 侧仍按「对账日期 + 对账金额」匹配（v3.0 不变）。

旧草稿若 `summary` 里没有 `sdms_check_num`，详情显示「—」；有 `check_head_id` 时链接仍可用（标签回退为头表 id）。要补单号需重新走一次 SDMS 校验（重新生成草稿）。

### 4.2 详情展示与跳转

详情「基本信息」增加一行：**SDMS对账单**。

- 展示文本：`check_num`（没有则「—」或回退 `check_head_id`）。
- 有 `check_head_id` 时做成超链接，交互对齐客户订单的 SDMS 销售订单（`ErpOrderLabel` + 系统浏览器打开）。

URL 模板（`{sdmsWebBaseUrl}` 与客户订单相同，测试默认 `http://192.168.99.35:8080`）：

```text
{sdmsWebBaseUrl}/sdms/check/sdms_check_cust_headers/sdmsCheckCustHeaders.do?method=view&fdId={check_head_id}
```

示例：`http://192.168.99.35:8080/sdms/check/sdms_check_cust_headers/sdmsCheckCustHeaders.do?method=view&fdId=36775`

---

## 5. O3 发票上传到 SDMS 对账单

### 5.1 何时传

沿用 v3.01 S7：客服选发票 **不** 跑 RPA；点 **提交审核** 后，一次 RPA 在同一浏览器会话里扫描并提交 SRM。

SRM 提交 **成功** 之后，由 **Task 服务 HTTP 上传** 同一批本机文件到 SDMS 附件服务（不新做 RPA，避免用工号变成门户登录名）。

```text
选发票（本机，不跑 RPA）
  → 提交审核
      → RPA：SRM 扫描 + 提交
      → 成功后 Task：HTTP 把发票挂到 SDMS 对账单
```

### 5.2 接口（对账单仍走附件服务；客户订单已换 SDMS SO）

对账单发票继续 `POST {附件服务}/upload`（`flag=SDMS_ARR`）。客户订单签章合同自 **v2.02 R4 / Flow 1.2.2** 起改为 SDMS `uploadAttachment` + OAuth，**不再与本文同一 URL**。

| 参数 | 对账单（本文） | 客户订单（v2.02 R4 对照） |
| --- | --- | --- |
| 地址 | 附件服务 `/upload`（测试默认 `http://api.doc.uat.smart-core.com.hk`） | `POST /core/api/srm/so/uploadAttachment`（OAuth 与建销售订单相同） |
| `flag` | **`SDMS_ARR`（固定）** | `SDMS_SO1` |
| 单号字段 | `order_number` = SDMS **`check_num`** | `custPoNumber` = 客户订单号 |
| `uploadUrl` | 无（本接口即上传地址） | **必填** `http://api.doc.uat.smart-core.com.hk/upload` |
| `username` | **当前 AutoTask 登录账号**（即员工工号） | 当前 Auth 登录账号（工号） |
| `filename` / `file` | 提交审核时选中的发票文件（可多份，逐个 POST） | `filename`=客户订单号；`file`=签章合同 PDF |

Task 配置项（无密钥）：`SDMS_ATTACHMENT_API_BASE_URL`、`SDMS_ATTACHMENT_FLAG=SDMS_ARR`。

### 5.3 工号怎么取

UserCache 目前没有独立「工号」列，**不为此加 DDL**。

提交审核时 Task 用当前请求的 Auth `/me`：优先 `username`，否则 `name`。该值写入提交任务 `input.sdmsUsername`，finish 钩子上传时使用。

取不到工号时：SRM 已成功则本地仍记 **已完成**；`last_error` 说明 SDMS 未传上，不回滚 SRM。

### 5.4 失败与重试

| 情况 | 本地阶段 | `last_error` |
| --- | --- | --- |
| SRM 提交失败 | 仍待上传发票 / 提交审核 | SRM 失败原因（v3.01 不变） |
| SRM 成功、SDMS 附件失败或缺少 `check_num`/工号 | **已完成**（不回滚 SRM） | 说明发票未传到 SDMS |
| 两者都成功 | 已完成 | 清空 |

本期 **不做** 独立「仅重传 SDMS」按钮；需要时客服按 `last_error` 手工补传，或产品后续再加。

本机路径约束与现有 RPA `set_input_files` 相同：Task 进程必须能读到客服选的文件（当前联调是同一台 Windows）。

---

## 6. 已确认

1. 详情叫对账明细；填单页仍叫收货明细。
2. `check_num` 进 `summary`，不新增数据库列、不执行迁移。
3. SDMS 查看页 `fdId` = `check_head_id`；展示文本优先 `check_num`。
4. SDMS 附件在 SRM 提交成功之后由 Task HTTP 上传；`flag=SDMS_ARR`，`order_number=check_num`。
5. `username` = AutoTask 登录账号（工号）；Auth `/me` 的 `username` 优先于 `name`。
6. SDMS 附件失败不撤销已完成；只记 `last_error`。

---

## 7. 明确不做

- 不新开 Cursor Plan 文件。
- 不把扫描和提交再拆成两次 RPA。
- 不把 `check_num` 当成 SRM 匹配键。
- 不为 `check_num` / 工号加表字段或执行 Alembic。
- 不新做「上传发票到 SDMS」RPA Flow。
- 本期不做 SDMS 附件失败后的一键重传。
- 生成页「收货明细」不改名。
