# AutoTask 正式上线操作清单

| 项 | 内容 |
| --- | --- |
| 状态 | **2026-08-28**：新应用 + **新空库**。先做成和当前**正式演练**一样，冒烟通过后再切真上线 |
| 场景 | 测试 `.env` 当模板拷走，只改库和本机接线；**不拷**测试业务数据 |
| 业务口径 | 演练与上线同一份正式 Flow。差别只在 Binding / `.env`。见 [v4.1 SOP](./AutoTask%20v4.1%20天地伟业正式演练与上线SOP.md) |
| 原则 | 空库建表，**不开**开发种子。密钥不进本文、不进 Git。 |

客服日常点什么看 v4.1。本文是新环境开张时谁动手。

---

## 0. 两段，不要一步到位

```text
阶段 A  新环境 = 正式演练克隆（测 SDMS/ERP、样例扫单、生成/提交 dryRun）
        ↓ 你确认 SOP 能跑、SRM 没被误写
阶段 B  改成真上线（收掉样例单、关 dryRun、SDMS/ERP 切生产、开调度）
```

阶段 A 的成功标准是**演练成功**：登录到了、按钮找到了、该点的点了、不该点的没点。  
阶段 B 的成功标准是 **SRM 状态按 SOP 变了**。

不要把测试库整库拷过来。任务、流程实例、对账单都在新库从零来。

---

## 1. 谁干什么

| 谁 | 负责 |
| --- | --- |
| **你** | 拷 `.env` 并改新库接线；Client 建门户；口头授权迁库、阶段 B 关闸 / 切生产基址 / 开调度 |
| **助手** | 发 Flow、建模板、按阶段绑 Binding（本机能连上目标 Task / Engine 时直接做） |
| **客服** | 登录后按 SOP 做业务 |
| **Auth** | 人、组织、角色（本仓库外） |

红线（两阶段都有效）：

1. `SEED_DATA_ENABLED` 必须 **false**。
2. 演示包不要绑正式站 `https://supplier.tiandy.com`。
3. 阶段 A 会改正式 SRM 的步骤必须留 `dryRun`。
4. 演示/清数脚本阶段 B 不用。
5. 助手**不会**在未口头授权时：对目标库 `alembic upgrade`、开调度、去掉 `dryRun`、把 SDMS/ERP 切到生产。

---

## 2. `.env` 怎么用测试那份

可以拷测试 `service/.env`、`rpa-engine/.env` 当模板，**另存一份给新环境**（不要覆盖丢掉测试机那份）。然后只改接线，阶段 A **不要**改 SDMS/ERP。

拷完后必改（示例，值以你现场为准）：

| 文件 | 必改 | 阶段 A 保持测试值 |
| --- | --- | --- |
| Task | `DATABASE_URL` 指向**新库**；`PUBLIC_BASE_URL` / Artifact 基址改成 Client 能访问的新 Task 地址；`RPA_ENGINE_BASE_URL` 对新 Engine | `SEED_DATA_ENABLED=false`、`SKIP_AUTO_MIGRATE=1`、`SUCCESSOR_JOB_ENABLED=true`；`SMC_*` / `SDMS_*` / `ERP_*` **仍测环境** |
| Engine | `DATABASE_URL` 同新库（schema `rpa_engine`）；`TASK_API_BASE_URL` 对新 Task；MinIO 用新环境 bucket（先空着） | `CREDENTIAL_RESOLVER_MODE=disabled`；Worker / Runtime 开 |
| Client | 登录页 / 安装包指向**新** Auth（若 Auth 也换了）和**新** Task | — |

`JWT_SECRET` 必须与这套环境的 Auth 一致。`SCAN_JOB_ENABLED` / `SIGN_POLL_JOB_ENABLED` 可不管，扫单/回签看调度中心。

本机不要用「已经改成新库」的 `.env` 随手启旧测试 4520：进程会连新库。两套文件分开，要用哪套说一声。

---

## 3. 推荐顺序

```text
你    新库建好（空库 nodeskclaw_task）；起 Auth/Task/Engine；.env 按第 2 节改完
你    口头授权迁库：Task alembic upgrade head；Engine CREATE SCHEMA rpa_engine 后再 alembic upgrade head
你    Client 连新环境，建门户「天地伟业-芯云-正式演练」，测试打开能进正式 SRM

你    对助手说：对着新环境按正式演练发 Flow、绑这个门户
助手  发布正式包 → 建模板 → 按阶段 A 绑 Binding（样例扫单、写步骤 dryRun、调度先关）
你    重启新环境 4520（建议 4610）
你    按正式演练冒烟（第 6 节）

之后  你确认没问题，口头授权阶段 B：收样例单、关 dryRun、.env 切生产、开调度
```

模板 / Binding / Flow Version 的 UUID **不要抄测试库**。本环境重新发、重新绑。Task 按 **组织 + 门户名称 + 模板 code** 找 Binding。

---

## 4. 空库迁库（须你授权）

Auth 可登录、组织已有人、至少一名模块管理员。

PostgreSQL：新库名以 `.env` 为准（当前阶段 A 为 `rpa_autotask`）。Task 表在 `public`；Engine 表在同库 schema `rpa_engine`。MinIO 的 Flow bucket **预先建好、先空着**。Task 磁盘 `ARTIFACT_LOCAL_DIR` 要持久（发票落这里）。

空库注意：Task 第一条 Alembic 是 `metadata.create_all`（按**当前**模型建全表），后面的增量修订会撞已有索引。空库不要指望 `alembic upgrade head` 一路跑完。正确做法：

```powershell
# 1) Task：建当前全表，并把 alembic 标到 head
cd d:\work_space260811\autotask-workspace\service
uv run python scripts\_bootstrap_empty_task_schema.py
uv run alembic stamp head
uv run alembic current
# 期望 head：b8c9d0e12f51

# 2) Engine：先有空 schema
# CREATE SCHEMA IF NOT EXISTS rpa_engine;
cd d:\work_space260811\autotask-workspace\rpa-engine
$env:PYTHONPATH = "d:\work_space260811\autotask-workspace\rpa-engine\src"
# Engine venv 的 greenlet 若被 4610 锁住，改用 service 的 python：
d:\work_space260811\autotask-workspace\service\.venv\Scripts\python.exe -m alembic upgrade head
d:\work_space260811\autotask-workspace\service\.venv\Scripts\python.exe -m alembic current
# 期望：20260713_0001
```

Task 迁完后再启 4520。Engine 迁完后再 `DATABASE_ENABLED=true` 起 4610。启动日志应看到跳过种子、后继任务已启动、Binding 调度器已启动。

---

## 5. 阶段 A：做成正式演练

对照当前测试机上的「天地伟业-芯云-正式演练」。Flow 同一套正式包，Binding 同一套闸。

### 5.1 你：建门户

名称先用演练名，地址正式 SRM。密码当场填。不要在 SRM 里手点保存/签章/生成/提交。告诉助手**门户准确名称**。

| 字段 | 填什么 |
| --- | --- |
| 名称 | `天地伟业-芯云-正式演练`（阶段 A 就用这个，和现网演练对齐） |
| 地址 | `https://supplier.tiandy.com` |
| 登录账号 / 密码 | 真实账号 |
| 客户编号 / 名称 | SDMS 编码 + 建单抬头 |
| 业务实体 / OU | 我方公司全称 + 公司编号 |
| 归属人 | 实际负责的客服 |

「测试打开」能进 SRM 即可。

### 5.2 助手：发包 + 绑 Binding（阶段 A）

空 Registry 必须在本环境重新发布。发布脚本默认 `http://127.0.0.1:4610`，打新 Engine 时改地址。

| 节点 | 模板 code | 正式包 | 阶段 A Binding |
| --- | --- | --- | --- |
| 扫待签章 | `srm_scan_pending_orders` | **1.1.3** | `searches` 两条（待签章 + 样例单）；`schedule` 先 `enabled: false` |
| 建 SDMS | `srm_prepare_erp_order` | **1.2.20** | **不设** `dryRun`（否则拦住我们自己的 SDMS） |
| 填交期 | `srm_fill_line_delivery_date` | 正式包未验收 | **不要绑** |
| 签章 | `srm_sign_order` | 同上 | **不要绑** |
| 回签 | `srm_check_reply_status` | **1.1.4** | `schedule` 先关 |
| 下合同 | `srm_upload_order_attachment` | **1.3.3** | **不设** `dryRun` |
| 查收货 | `srm_stmt_query_receipts` | **1.1.3** | **不设** `dryRun` |
| 生成对账单 | `srm_stmt_generate` | **1.1.0** | **`dryRun: true`** |
| 扫描发票 | `srm_stmt_upload_invoice` | **1.1.2** | **不设** `dryRun` |
| 提交审核 | `srm_stmt_submit_review` | **1.1.5** | **`dryRun: true`** |

扫单阶段 A（和现网演练一致；换单号只改第二条 `poNo`）：

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "searches": [
    { "replyStatus": "待签章" },
    { "poNo": "POJS2607170008", "treatAsPending": true }
  ],
  "schedule": {
    "enabled": false,
    "cron": "0 8 * * *",
    "processName": "客户订单",
    "actionName": "扫单"
  }
}
```

回签：`cron` 先写成 `*/30 * * * *`，`actionName` `回签轮询`，同样先关。之后改 cron/开关只去调度中心。

`config.portalUrl` = 该门户地址。演示门户（`192.168.102.247`）不要在这个新环境建，除非你明确还要演示站。

绑完后重启 **4520**（建议 4610）。

---

## 6. 阶段 A 冒烟（你确认没问题）

- [ ] Client 连的是**新** Auth/Task（不是旧测试 4520）
- [ ] 种子关、后继任务开、库已是 head `b8c9d0e12f51`
- [ ] Engine Worker/Runtime 开，凭据 `disabled`
- [ ] Flow 在**本环境**发布，Binding 不是从测试库抄的 UUID
- [ ] 门户能测试打开正式 SRM
- [ ] `.env` 里 SDMS/ERP 仍是**测试**基址
- [ ] 扫单仍有样例第二条 + `treatAsPending`
- [ ] 生成 / 提交仍 `dryRun`
- [ ] 调度仍关
- [ ] 发票目录在 Task 服务器可写
- [ ] 手动扫单能扫到样例单（或待签章为空后再走样例）
- [ ] 建单失败可点重试（会走当前 Binding 的 Flow 版本）
- [ ] 生成对账单不真点门户生成；提交审核不真点门户提交

客服只确认：自己工号能登录、能看见该门户、按 SOP 操作。填交期/签章正式包未绑，样例已回签单会跳过这两步，这是演练预期。

---

## 7. 阶段 B：再切真上线（必须你口头授权）

包不用重发。改 Binding 和 `.env`。

| 步 | 做什么 |
| --- | --- |
| 1 | 门户可改名（不要再叫「…演练」），地址仍正式 SRM |
| 2 | 扫单 `searches` **只留** `{ "replyStatus": "待签章" }`，删掉样例 `poNo` / `treatAsPending` |
| 3 | Task `.env` 的 `SDMS_*` / `ERP_*` 改成**生产**，重启 4520 |
| 4 | 空列表扫单成功（没有待签章 = 成功，不再扫样例） |
| 5 | 有真实待签章再扫；缺填交期/签章正式包时单可能停在建 SDMS 之后 |
| 6 | 去掉生成、提交的 `dryRun` |
| 7 | 填交期/签章正式包就绪后再关闸、再绑 |
| 8 | 调度中心打开该门户扫单、回签 |

上线成功看 **SRM 状态变了**，不是只看任务 SUCCESS。

---

## 8. 已知缺口

1. 填交期/签章正式包未按真实待签章绑上。演示 1.0.3 禁止绑正式站。
2. Artifact 下载地址必须给 Client 可达主机，不要留 `127.0.0.1`。
3. 发票在 Task 本机磁盘，生产要备份该目录。
4. 正式环境建议手工迁库，再 `SKIP_AUTO_MIGRATE=1` 启动。

---

## 9. 相关文档

| 要查 | 看 |
| --- | --- |
| 客服每步点什么 | [v4.1 SOP](./AutoTask%20v4.1%20天地伟业正式演练与上线SOP.md) |
| 演练/上线同一份包 | [正式门户 Flow 演练与上线](./正式门户%20Flow%20演练与上线.md) |
| 密码和 SDMS 基址 | [v5.0](./AutoTask%20v5.0%20门户密码.md) |
| 谁能看见门户 | [v5.1](./AutoTask%20v5.1%20权限.md) |
| 调度 | [v5.2](./AutoTask%20v5.2%20调度中心.md) |
| 发票传到 Task | [v5.3](./AutoTask%20v5.3%20对账单发票上传.md) |
| 接口调用日志 | [v5.4](./AutoTask%20v5.4%20接口调用日志.md) |
