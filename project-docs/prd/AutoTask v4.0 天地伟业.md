# AutoTask v4.0 天地伟业：演示门户切正式演练

| 项 | 内容 |
| --- | --- |
| 版本 | **v4.0** |
| 状态 | **方案已确认（2026-08-18）**；实施前以本文为准 |
| 基线 | 客户订单 v2.02；对账单 v3.0 / v3.01 / v3.02 |
| 计划 | [`.cursor/plans/v4.0_天地伟业_正式演练_2026-08-18.plan.md`](../../.cursor/plans/v4.0_天地伟业_正式演练_2026-08-18.plan.md) |
| 原则 | 正式 SRM **不写对方数据**；AutoTask 本地 **读步骤真推进、写步骤停在当前阶段并标「演练未提交」** |

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

### 0.2 红线

1. 不能改对方 SRM 业务数据。
2. 目前找不到待签章客户订单；轮询扫不到单，不能假装 SRM 里有待签章。
3. 填写交期可以操作到输入框，**不能保存**。
4. 收货列表有数据，**不能点生成对账单**。
5. 对账列表已有一条未对账：可以进「收货应付」详情；扫描发票可以做，**不能提交审批**。
6. 节点 4 若真下到签章合同，**默认不上传 SDMS**。

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

**正式门户只读真跑 + 写步骤到按钮即停 + 缺数据用本地影子单。**

本地状态（已选）：

- 读步骤成功：按现行规则推进（扫单空列表也算成功；查收货出数；进已有未对账单）。
- 写步骤成功但 `committed: false`：**阶段不往前**，不把交期行标成已写入、不把对账单改成未对账/已对账。
- 在流程实例 `summary.drill` 记下演练证据；Client 显示琥珀色徽章 **「演练未提交」**，不当失败卡点。

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

### 3.2 成功判据

演练成功 **不是**「SRM 状态变了」，而是：登录成功、页面/表头/按钮定位成功、写按钮未点击、Artifact 有按钮截图、output.committed === false。

---

## 4. 两条链怎么跑

### 4.1 客户订单

| 步骤 | 正式 SRM | 演练 | 本地状态 |
| --- | --- | --- | --- |
| 登录 | 选择器/验证码与演示不同 | 真登录；未知验证码走 `WAITING_HUMAN` | — |
| 扫待签章 | 当前无单 | 进订单列表并筛选；**空列表 SUCCESS** | 不创建实例（现行 `create_from_scan` 对空列表已是空操作） |
| 填交期 | 无待签章则可能无保存按钮 | 有可编辑详情则填框、定位保存后停；没有保存按钮则记「选择器未覆盖」，不编造成功 | 行不标 WRITTEN；阶段不进 DATES_COMPLETE |
| 签章 | 同上 | 定位签章按钮后停 | 不进 SIGN_REQUESTED |
| 回签轮询 | 无待回签实例 | 对影子单或真实已回签 PO **只读**探测 | 未发现已回签则不触发归档；空结果不算失败 |
| 下合同 | 可能有已回签 | 有单才下载到本地 | **不上传 SDMS**；不进 ARCHIVED |

没有待签章时，**不靠轮询变出单**。需要 Client 能往下点时，用影子实例（`summary.drill.shadow: true`），biz_key 尽量用探测到的真实已回签 PO。

### 4.2 对账单

| 步骤 | 正式 SRM | 演练 | 本地状态 |
| --- | --- | --- | --- |
| 收货列表查询 | 有大量未提交收货 | **完整真跑**（切正式后的主验收） | 填单页展示行；尚未点生成则不落账单 |
| SDMS 金额校验 | 我方接口 | 真调；不写 SRM | 校验失败仍不落库（v3.0 不变） |
| 勾选 + 生成 | 不能点生成 | 勾选并定位「生成对账单」后停 | 若 SDMS 已通过，仍可落 **待生成草稿**；生成 RPA 演练成功后 **仍为待生成**，不改未对账 |
| 未对账详情 | 已有 1 条 | 用这条当「生成后」替身，进收货应付 | 影子账单 `check_status=UNCHECKED`，匹配键 = 对账日期 + 对账金额 |
| 扫描发票 | 允许 | 真扫描 | 刷新后 SRM 附件消失是预期，不修 |
| 提交审批 | 不能提交 | 定位按钮后停 | 不改已对账 / 审批中；不传发票到 SDMS |

生产规则「扫描和提交必须同一次 RPA」仍然有效。演练闸里故意拆开：扫可以做，提交必须停。`dryRun=false` 时行为与 v3.01 完全一致。

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

### 5.2 Flow 输出（写步骤）

在现有 schema 上增加：

```json
{
  "committed": false,
  "dryRun": true,
  "blockedAction": "generate_statement"
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

脚本 `service/scripts/seed_tiandi_drill.py`（默认预览，`--yes` 才写库）：

- 入参：portal_account_id、可选已回签 PO、未对账的对账日期与金额。
- 创建带 `summary.drill.shadow=true` 的客户订单实例和/或 `statement_bills`。
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
| `rpa-flows/` | 写步骤四包（填交期、签章、生成、提交审核）加刹车；扫单/查收货/回签探测按正式选择器适配；提交审核演练允许扫描、禁止提交 |
| `service/` | 租约带 `dryRun`；finish 钩子尊重 `committed: false`；详情 DTO `drillUncommitted`；影子种子脚本 |
| `app/` | 列表/详情琥珀色「演练未提交」；扫单空结果友好文案 |
| 演示 Binding | 不改 URL、不加 `dryRun` |

节点 4 下载包：演练 Binding 下跳过 SDMS 上传（读 `dryRun` 或 input 开关），只保留本地 Artifact。

---

## 8. 验收清单

给用户前，下列全部成立：

- [ ] 正式账号能登录（自动或一次人工验证码）。
- [ ] 收货列表查询拉到真实未提交行。
- [ ] 生成：勾选成功，按钮截图在，SRM 未新增对账单。
- [ ] 用现有未对账单能进收货应付；发票能扫描；提交按钮截图在，SRM 仍为未对账。
- [ ] 客户订单扫单空列表 SUCCESS，Client 不报错。
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

未列出的客户订单、对账单规则继续以 v2.02 / v3.0 / v3.01 / v3.02 为准。v4.0 只增加：正式门户演练闸、空扫单视为成功、影子数据、Client 演练徽章。
