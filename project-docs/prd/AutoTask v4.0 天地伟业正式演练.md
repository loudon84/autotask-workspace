# AutoTask v4.0 天地伟业：演示门户切正式演练

| 项 | 内容 |
| --- | --- |
| 版本 | **v4.0** |
| 状态 | 方案基线（2026-08-18）；**现行操作说明见 [v4.1 SOP](./AutoTask%20v4.1%20天地伟业正式演练与上线SOP.md)** |
| 基线 | 客户订单 v2.02；对账单 v3.0 / v3.01 / v3.02 |
| 计划 | [`.cursor/plans/v4.0_天地伟业_正式演练_2026-08-18.plan.md`](../../.cursor/plans/v4.0_天地伟业_正式演练_2026-08-18.plan.md) |
| 原则 | 正式 SRM **只读+下载合同**；SDMS（测试环境）**真写**；写步骤停在按钮前并标「演练未提交」 |
| Flow 演练/上线 | [正式门户 Flow 演练与上线](./正式门户%20Flow%20演练与上线.md)：同一份正式包，差别进 Binding |

---

## 0. 背景

天地伟业两个单据功能已在演示门户初步测通。演示门户是 mock：有 `data-rpa`、固定验证码文件名映射、可随意保存/签章/生成。正式 SRM 页面、数据、写权限都不同。

给用户前要在正式 SRM 上把客户订单、对账单两条链尽量跑全，同时遵守红线。

### 0.1 正式门户（公开信息）

| 项 | 值 |
| --- | --- |
| 地址 | `https://supplier.tiandy.com` |
| 登录账号 | `02556` |
| 业务主体 | 深圳市芯云信息科技有限公司 |

凭据只进现有 PortalAccount / credential 存储。**禁止**写入 Git、`PROJECT_CONTROL.md`、PRD、日志、截图文件名。

演示门户 Binding（`http://192.168.102.247:3000`）保留不动。正式账号单独建 Portal + Binding，不要覆盖演示环境。

### 0.2 红线（2026-08-19 用户确认）

1. 不能改对方 SRM 业务数据。
2. 目前找不到待签章客户订单；轮询扫不到单，不能假装 SRM 里有待签章。
3. 填写交期可以操作到输入框，**不能保存**。
4. 收货列表有数据，**不能点生成对账单**。
5. 对账列表已有一条未对账：可以进「收货应付」详情；扫描发票可以做，**不能提交审批**。
6. 节点 4：正式站订单均为已回签，**可以下载签章合同并上传 SDMS**（SDMS 为测试环境，允许真写）。
7. 建 SDMS 销售订单：从正式站下载订单后**真建**（SDMS 测试环境允许）。

---

## 1. 目标与非目标

**目标：** 在正式 SRM 上验证登录、菜单、列表、详情、勾选、按钮定位，以及 AutoTask 两条 SOP 在 Client 上能走完可读部分；写操作走到提交按钮前停下并留截图证据。

**非目标：**

- 本期不上线「对正式 SRM 真提交」。
- 不把演练闸做成给客服用的长期产品开关（默认关；只挂正式 Portal Binding）。
- 不删演示门户链路。
- 不为演练新增数据库列或执行 DDL。

---

## 2. 已确认方案

**正式门户只读真跑 + 写步骤到按钮即停 + SDMS 测试环境真写。**

本地状态（已选）：

- 读步骤成功：按现行规则推进（扫单空列表也算成功；查收货出数；进已有未对账单）。
- 写步骤成功但 `committed: false`：**阶段不往前**，不把交期行标成已写入、不把对账单改成未对账/已对账。
- 在流程实例 `summary.drill` 记下演练证据；Client 显示琥珀色徽章 **「演练未提交」**，不当失败卡点。
- **SDMS 写操作（建销售订单、上传合同附件）是真写**，不受 `dryRun` 限制；`dryRun` 只拦对 SRM 的写。

不采用：只做探测脚本、Client 仍对着演示门户。  
不采用：本地假装已经签章/已生成，给用户看假完成态。

---

## 3. 架构

```text
PortalAccount（正式天地伟业，独立于演示）
    └─ WorkflowBinding.config
           portalUrl = https://supplier.tiandy.com
           dryRun    = true          ← 仅此 Binding；演示 Binding 无此键或 false
                 │
                 ▼
Task 租约 config.dryRun → Engine ctx.config.dryRun
                 │
                 ▼
Flow：导航 / 填写 / 勾选 / 定位按钮
      dryRun=true 时不 click 保存、签章、生成、提交审批
      Playwright 拦截非登录、非查询、非（允许的）发票扫描写请求
      返回 SUCCESS + committed: false + 截图
                 │
                 ▼
finish 钩子：committed=false → 不改 stage / check_status
             只写 summary.drill
```

### 3.1 三道写闸

1. **最后一击：** 保存、签章、生成对账单、提交审批四处 `click` 包在 `if not dry_run`。演练只等待按钮可见且可点，截图后返回。
2. **网络保险：** `page.route` 拦截 `POST/PUT/PATCH/DELETE`。放行登录、验证码、查询；提交审核演练额外放行发票扫描上传。漏点按钮时请求仍被 abort。
3. **Binding 默认关：** 只有正式天地伟业 Binding 设 `dryRun: true`。真上线先把该键改为 `false` 或删除，并经明确授权。

**注意：** `dryRun` 只拦对 SRM 的写。SDMS（测试环境）的写操作（建销售订单、上传合同附件）**不受 dryRun 限制**，是真写。

### 3.2 成功判据

演练成功 **不是**「SRM 状态变了」，而是：登录成功、页面/表头/按钮定位成功、写按钮未点击、Artifact 有按钮截图、output.committed === false。

---

## 4. 两条链怎么跑

### 4.1 客户订单

| 步骤 | 正式 SRM | 演练 | 本地状态 |
| --- | --- | --- | --- |
| 登录 | 选择器/验证码与演示不同 | 真登录；未知验证码走 `WAITING_HUMAN` | — |
| 扫待签章 | 当前无单 | 待签章查询后导出 Excel；无结果则 Binding `searches` 再按样例订单编号导出 | 用 Excel 建实例；生产 Binding 只留待签章。见 [演练与上线](./正式门户%20Flow%20演练与上线.md) |
| 建 SDMS 销售订单 | 从正式站下载订单 | **真建 SDMS**（测试环境允许） | 阶段推进到 SDMS_CREATED |
| 填交期 | 无待签章则可能无保存按钮 | 有可编辑详情则填框、定位保存后停；没有保存按钮则记「选择器未覆盖」，不编造成功 | 行不标 WRITTEN；阶段不进 DATES_COMPLETE |
| 签章 | 同上 | 定位签章按钮后停 | 不进 SIGN_REQUESTED |
| 回签轮询 | 无待回签实例 | 对影子单或真实已回签 PO **只读**探测 | 未发现已回签则不触发归档；空结果不算失败 |
| 下合同 | 已回签单可下载 | 下载签章合同到本地 | **真上传 SDMS**；进 ARCHIVED |

没有待签章时，**不靠轮询变出单**。需要 Client 能往下点时，用影子实例（`summary.drill.shadow: true`），biz_key 尽量用探测到的真实已回签 PO。

**建 SDMS 销售订单 Binding 不要设 `dryRun`**（那会拦住我们自己的 SDMS POST）。`dryRun` 只挂填交期/签章/生成/提交那些包。

### 4.2 对账单

| 步骤 | 正式 SRM | 演练 | 本地状态 |
| --- | --- | --- | --- |
| 收货列表查询 | 有大量未提交收货 | **完整真跑**（切正式后的主验收） | 填单页展示行；尚未点生成则不落账单 |
| SDMS 金额校验 | 我方接口 | 真调；不写 SRM | 校验失败仍不落库（v3.0 不变） |
| 勾选 + 生成 | 不能点生成 | 勾选并定位「生成对账单」后停 | 若 SDMS 已通过，仍可落 **待生成草稿**；生成 RPA 演练成功后 **仍为待生成**，不改未对账 |
| 未对账详情 | 已有 1 条 | 用这条当「生成后」替身，进收货应付 | 影子账单 `check_status=UNCHECKED`，匹配键 = 对账日期 + 对账金额 |
| 扫描发票 | 允许 | 真扫描，回写到 Client 供核验 | 本地可有发票号/总额；门户刷新附件消失是预期 |
| 提交审批 | 不能提交 | 再扫一次，必须与页面一致；定位按钮后停 | 不一致则失败不点提交；一致也不改已对账（dryRun） |

生产：客服先扫后核，再点提交。提交 RPA 二次扫描必须等于页面已核对的发票号/总额。`dryRun=false` 时一致才点门户提交。

**2026-08-21 会话修订（相对本节原文）：**

1. 生成演练成功只证明「找到生成按钮」。门户**没有**对应未对账单。那张本地待生成草稿是相对 SRM 的假数据，**禁止**把它改成未对账、也禁止拿它去上传发票。
2. 下一节点必须另插影子账单：门户当前那条未对账的日期+金额。脚本是 `seed_official_unchecked_statement.py`（不是 `seed_tiandi_drill.py`，后者只种客户订单）。
3. Client 详情先「扫描发票」回写发票号/总额供核验，再点「提交审核」。提交表示页面结果已通过。
4. 正式站**要绑** `srm_stmt_upload_invoice` 1.1.0（第一次扫描，无 dryRun）。提交仍 1.1.1 + `dryRun: true`。二次扫描必须与页面发票号/总额一致，否则不点提交。
5. 演练提交成功后本地仍待上传发票 / 未对账；不传发票到 SDMS。上线同一包，Binding 去掉 `dryRun` 才真点提交。

---

## 5. 数据与接口

### 5.1 Binding.config

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "dryRun": true,
  "browserSession": { "mode": "MANAGED", "headless": true, "channel": "chrome" }
}
```

Task 租约把 `dryRun` 放进 `config`（与 `portalUrl` 并列）。Engine 写入 `ctx.config["dryRun"]`。Flow 用 Engine 提供的 `is_dry_run(ctx)` 读取。缺省 `false`。

**Binding 配置策略：**
- 建 SDMS 销售订单 Flow：**不设 `dryRun`**（或 `dryRun: false`），因为要真写 SDMS。
- 填交期/签章/生成对账单/提交审批 Flow：**设 `dryRun: true`**，只拦对 SRM 的写。
- 扫单/查收货/回签探测/下载合同 Flow：**不设 `dryRun`**，只读操作不需要闸。

### 5.2 Flow 输出（写步骤）

在现有 schema 上增加：

```json
{
  "committed": false,
  "dryRun": true,
  "blockedAction": "generate_statement | submit_review"
}
```

`committed` 缺省视为 `true`（兼容旧包）。finish 钩子：**仅当 `committed is False` 时走演练分支**。

### 5.3 summary.drill（无新列）

写入 `process_instances.summary`：

```json
{
  "drill": {
    "uncommitted": true,
    "shadow": false,
    "step": "srm.stmt.generate",
    "blockedAction": "generate_statement",
    "at": "2026-08-18T11:00:00+00:00"
  }
}
```

详情 DTO 增加只读 `drillUncommitted`（从 summary 派生）。Client 徽章读该字段。不把演练成功写入 `last_error_*`，避免被当成失败卡点。

### 5.4 影子数据

客户订单：`service/scripts/seed_tiandi_drill.py`（默认预览，`--yes` 才写库）

- 入参：portal_account_id、可选已回签 PO。
- 创建带 `summary.drill.shadow=true` 的客户订单实例。
- 不写凭据、不调 SRM。

对账单未对账替身：`service/scripts/seed_official_unchecked_statement.py`（2026-08-21 从「一个脚本兼顾订单/对账单」拆出）

- 入参：`--check-date`、`--check-amount`（必须与门户那条未对账一致）、可选 portal_account_id。
- 创建 `statement_bills.check_status=UNCHECKED`、流程阶段 `STMT_PENDING_INVOICE`，`summary.drill.shadow=true`。
- 不把生成演练的待生成草稿改成未对账。
- 不写凭据、不调 SRM。

---

## 6. 选择器与登录

演示包依赖 `[data-rpa=…]` 和验证码文件名映射。正式站没有这些。

**实施闸：先只读探测，再改编译器。** 探测脚本只读 DOM、不填可提交表单（登录除外）、不点保存/签章/生成/提交。产物（选择器候选、表头、按钮文案、登录是否有验证码）写入 `rpa-engine/runtime-cache/` 本地文件，不进 Git。

登录策略：

- 能自动过验证码则自动过。
- 不能则 `HUMAN_VERIFICATION_REQUIRED`，人工一次后会话复用（现行生成 Flow 已有会话复用）。
- 协议勾选若存在则勾。

禁止把正式验证码答案或密码写进 Flow 源码。

---

## 7. 范围（按仓库）

| 仓库 | 做什么 |
| --- | --- |
| `rpa-engine/` | `is_dry_run` + `install_write_guard`；租约 config 透传 `dryRun`；正式站只读探测脚本 |
| `rpa-flows/` | 写步骤四包（填交期、签章、生成、提交审核）加刹车；扫单/查收货/回签探测按正式选择器适配；提交审核演练允许扫描、禁止提交；**建 SDMS 销售订单 Flow 1.2.7 已适配正式站选择器（不设 dryRun）** |
| `service/` | 租约带 `dryRun`；finish 钩子尊重 `committed: false`；详情 DTO `drillUncommitted`；影子种子脚本 |
| `app/` | 列表/详情琥珀色「演练未提交」；扫单空结果友好文案 |
| 演示 Binding | 不改 URL、不加 `dryRun` |

节点 4 下载包：正式站已回签单可下载签章合同并**真上传 SDMS**（测试环境允许）。

---

## 8. 验收清单

给用户前，下列全部成立：

- [ ] 正式账号能登录（自动或一次人工验证码）。
- [ ] 收货列表查询拉到真实未提交行。
- [ ] 生成：勾选成功，按钮截图在，SRM 未新增对账单。
- [ ] 用现有未对账单能进收货应付；发票能扫描；提交按钮截图在，SRM 仍为未对账。
- [ ] 客户订单扫单空列表 SUCCESS，Client 不报错。
- [ ] **建 SDMS 销售订单：从正式站下载 POJS2607170008，真建 SDMS 成功。**
- [ ] **下载签章合同：从正式站下载已回签合同，真上传 SDMS 成功。**
- [ ] 填交期/签章：有按钮则停在点击前；无按钮则明确失败码，不编造成功。
- [ ] Client 写步骤后仍停在原阶段，并显示「演练未提交」。
- [ ] 演示门户 Binding 仍指向演示 URL，回归不受影响。
- [ ] 日志/文档/截图文件名无密码。

待签章一旦出现：填交期/签章仍只准演练。真保存必须另开授权，并把该 Binding 的 `dryRun` 关掉。

---

## 9. 风险

| 风险 | 处理 |
| --- | --- |
| 正式登录/验证码与演示完全不同 | 探测为实施闸；未知验证码人工 |
| 无待签章，填/签页面结构未知 | 不编造成功；影子单只保证 Client 能点 |
| 勾选 checkbox 被网络闸误杀 | 勾选一般是 DOM，不是 API；若正式站勾选即 POST，探测后把该 API 加入拦截，勾选改成只验证 checkbox 可见 |
| 发票扫描后刷新附件消失 | 预期；不修 SRM |
| `dryRun` 忘记关闭就上线 | Binding 评审清单；真上线授权检查该键 |
| 网络闸误拦登录 | 登录 URL 白名单；探测时记录登录请求路径 |

---

## 10. 相对既有版本

未列出的客户订单、对账单规则继续以 v2.02 / v3.0 / v3.01 / v3.02 为准。v4.0 只增加：正式门户演练闸、空扫单视为成功、影子数据、Client 演练徽章、**建 SDMS 销售订单 Flow 1.2.7 适配正式站选择器**。

---

## 11. 实施状态（2026-08-20）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Engine dry_run 机制 | ✅ 完成 | `dry_run.py` + 租约透传 + 网络闸 |
| 正式站只读探测 | ✅ 完成 | 登录成功；订单/收货/对账列表表头已采集；无 `data-rpa` |
| 正式 Portal | ✅ 完成 | 「天地伟业-国际-正式演练」`fbf07b4e-…`，URL `https://supplier.tiandy.com` |
| 正式只读 Binding | ✅ 完成 | 扫单 / 回签探测 / 收货查询均为 **1.1.0 正式包**；未设 `dryRun` |
| 建 SDMS Flow 1.2.7 | ✅ 源码完成 | 正式站选择器适配；**未发布、未绑正式门户**（阶段 2） |
| 生成对账单 1.1.0 | ✅ 完成 | 正式 Binding `dryRun: true`；演示仍 1.0.7 |
| 提交审核 1.1.0 | ✅ 源码/发布 | 正式 Binding `dryRun: true`；扫描真做；演示仍 1.0.7 |
| 未对账影子种子 | ✅ 完成 | `seed_official_unchecked_statement.py`；需门户真实日期+金额 |
| 验收 | ⏳ 待做 | 种子写库后 Client 选发票点提交审核；门户仍未对账 |

**禁止混绑：** 演示门户（芯云test / 国际test）仍用扫单 `1.0.1`、回签 `1.0.0`、收货 `1.0.3`。正式 1.1.0 不得绑 `192.168.102.247`。

**下一步：** 对账单提交审核演练。先用 `seed_official_unchecked_statement.py` 按门户未对账日期+金额写库；Client 选发票后点「提交审核」。正式包 1.1.0 扫描真做、提交 dryRun 不 click。演示提交仍 1.0.7。

---

## 12. 相对原文的会话修订（便于反查 / 上线）

原文（§4.2 / §5.4）写「生成后用已有未对账当替身」和「`seed_tiandi_drill.py` 可种对账单」，但没有写清生成演练单与门户未对账是两张单。2026-08-21 确认并归档：

| 点 | 原文 | 现口径 |
| --- | --- | --- |
| 生成演练成功 | 可落待生成草稿 | 草稿保留；门户无对账单；**不得**把草稿改成未对账 |
| 未对账替身 | 用已有 1 条 | 另跑种子脚本，匹配键 = 门户那条的日期+金额 |
| 种子脚本 | `seed_tiandi_drill.py` 兼顾订单和 `statement_bills` | 订单仍用该脚本；对账单用 `seed_official_unchecked_statement.py` |
| Client 提交审核 | 能进详情、能扫描 | 先扫后核；点提交 = 页面发票已通过；二次扫描必须一致 |
| 上传发票包 | 曾写正式不绑 upload | **要绑** 扫描 1.1.0（无 dryRun）；提交 1.1.1 |
| 提交演练成功 | 不改已对账、不传 SDMS | 同；`committed: false`；阶段仍待上传发票 |
| 上线 | dryRun 改为 false | 同一份 submit 1.1.1，去掉 `dryRun` 才点门户提交 |

禁止混绑：演示门户提交仍 `1.0.7`。正式 1.1.0 不得绑 `192.168.102.247`。
