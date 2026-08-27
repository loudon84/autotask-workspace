# AutoTask 正式上线操作清单

| 项 | 内容 |
| --- | --- |
| 状态 | **2026-08-27**：你维护 `.env` 和门户；流程模板 / 发 Flow / Binding 仍由助手在本机对着目标环境执行（和开发期一样） |
| 场景 | 正式 **应用服务器新、数据库新** |
| 业务口径 | 演练与上线同一份正式 Flow。见 [v4.1 SOP](./AutoTask%20v4.1%20天地伟业正式演练与上线SOP.md) |
| 原则 | 空库建表，**不开**开发种子，**不拷**测试业务数据。密钥不进本文、不进 Git。 |

客服日常点什么看 v4.1。本文是空环境开张时谁动手。

---

## 0. 和开发期同一套分工

开发时流程、发 Flow、绑 Binding 本来就是助手在本机跑脚本（Engine `127.0.0.1:4610`、Task 库来自 `service/.env`）。上线可以继续这样，**不必你在 Client 里逐条点模板和 Binding**。

你只需要：

1. 让本机能访问正式 Task / Engine / 库（同一局域网或 VPN）。
2. 维护正式接线：`service/.env`、`rpa-engine/.env`（建议用**另一份**正式文件，不要把测试 `.env` 直接覆盖丢掉）。
3. 在 Client 建好门户（名称、地址、账号密码、客户编号、业务实体、OU、归属人），并「测试打开」能进 SRM。

助手在你说「对着正式环境做」之后执行：

- 发正式 Flow（发布脚本改成正式 Engine 地址，走同一套上传/校验/发布）
- 按门户名称建缺失的流程模板（code 固定）
- 按发布结果绑 Binding（调度先关；生成/提交先留 `dryRun`）
- 改完后提醒你重启正式 4520 / 4610

助手**不会**在未口头授权时：对生产执行 `alembic upgrade`、开调度、去掉 `dryRun`、把 SDMS 基址切到生产。这些和开发期写库脚本一样，要你先说可以。

不要把测试 `.env` 改成正式后再随手启本地 Task：本地进程会连正式库。正式文件单独放（例如 `.env.production`，不提交 Git），要用时说一声。

本机打不到正式 4520/4610 时，助手改不了远程进程，只能把命令写给你到服务器上跑。

---

## 1. 谁干什么

| 谁 | 负责 |
| --- | --- |
| **你** | 正式 `.env`；Client 里维护门户；口头授权迁库 / 关 `dryRun` / 开调度 |
| **助手** | 发 Flow、建模板、绑 Binding（本机能连上正式环境时直接做） |
| **客服** | 登录后按 SOP 做业务；以后改门户密码/归属人 |
| **Auth** | 人、组织、角色（本仓库外） |

红线：

1. `SEED_DATA_ENABLED` 必须 **false**。
2. 扫单 Binding **不要** `treatAsPending`、不要样例单号。
3. 演示包不要绑正式站。
4. 会改正式 SRM 的步骤，授权前保留 `dryRun`。
5. 演示/清数脚本上线不用。

---

## 2. 空库初始化（推荐顺序）

不要整库拷测试。

```text
你   正式服务器起库、起 Auth/Task/Engine；填正式 .env（种子关、后继任务开）
你   口头授权后：Task alembic upgrade head；Engine 先 CREATE SCHEMA rpa_engine，再在 rpa-engine 目录 alembic upgrade head
你   Client 连正式 Auth/Task，建门户并测试打开

你   对助手说：对着正式环境发 Flow、绑这个门户
助手 发布正式包 → 建模板 → 绑 Binding（调度关、写步骤 dryRun）
你   重启正式 4520（建议 4610）
你   手动扫单冒烟（无待签章 = 空列表成功）
之后 再口头授权关闸、开调度（第 7 节）
```

模板 UUID 不必和测试库相同。Task 按 **组织 + 门户 + 模板 code** 找 Binding。

---

## 3. A. 机房（你做一次）

Auth 可登录、组织已有人、至少一名模块管理员。Task 的 `JWT_SECRET` 与 Auth 一致。

PostgreSQL：新库 `nodeskclaw_task`。Task 表在默认 schema；Engine 表在同库的 schema `rpa_engine`（两套 Alembic，不是手工建九张表）。MinIO 的 Flow bucket **预先建好、先空着**。Task 磁盘 `ARTIFACT_LOCAL_DIR` 要持久（发票落这里）。

**Task `.env` 真正要想的只有这些：**

| 键 | 口径 |
| --- | --- |
| `DATABASE_URL` / `JWT_SECRET` / `NODESKCLAW_BACKEND_URL` / `RPA_ENGINE_BASE_URL` | 接线 |
| `SEED_DATA_ENABLED=false` | 必关 |
| `SKIP_AUTO_MIGRATE=1` | 先手工迁库再启动 |
| `SUCCESSOR_JOB_ENABLED=true` | 必开，否则节点不自动往下走 |
| `SMC_API_BASE_URL` / `SDMS_BASE_URL` / `ERP_*` / `SDMS_ATTACHMENT_API_BASE_URL` | 指向**生产**（切正式 SDMS 也要你点头） |
| `PUBLIC_BASE_URL` 和 Artifact 下载基址 | Client 能访问，不要 `127.0.0.1` |

`SCAN_JOB_ENABLED` / `SIGN_POLL_JOB_ENABLED` 可不管，扫单/回签看调度中心。

**Engine：** `DATABASE_ENABLED` + Worker + Runtime 都开；`CREDENTIAL_RESOLVER_MODE=disabled`；MinIO 开。SRM 密码不进 Engine。

**Client：** 登录页填正式 Auth + 正式 Task。

迁库须你授权，**两条命令、两套表，互不管**：

```powershell
# Task 表（门户、任务、对账单、调度…）
cd d:\work_space260811\autotask-workspace\service
uv run alembic upgrade head
uv run alembic current
# 期望 head：a7e4b2c81d09

# Engine 表（Flow Registry、Worker…）。先有空 schema，启动不会自己建表。
# 在库里执行一次：CREATE SCHEMA IF NOT EXISTS rpa_engine;
cd d:\work_space260811\autotask-workspace\rpa-engine
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
# 期望：20260713_0001
```

Task 迁完后再启 4520。Engine 迁完后再把 `DATABASE_ENABLED=true` 起 4610。启动日志应看到跳过种子、后继任务已启动、Binding 调度器已启动。

---

## 4. B. 发布正式 Flow（助手执行）

空 Registry 必须在本环境重新发布。Binding 钉这次发布结果，不要抄测试 UUID。发布脚本默认 `http://127.0.0.1:4610`，打正式时改成正式 Engine。

| 节点 | 模板 code | 正式包 | Binding 要点 |
| --- | --- | --- | --- |
| 扫待签章 | `srm_scan_pending_orders` | **1.1.3** | `searches` 只留待签章；`schedule` 先 `enabled: false` |
| 建 SDMS | `srm_prepare_erp_order` | **1.2.16** | 不设 `dryRun`；主表 `customerSubCode`/`orgCode` 来自门户 |
| 填交期 | `srm_fill_line_delivery_date` | 正式包未验收 | 不要绑演示 1.0.3 |
| 签章 | `srm_sign_order` | 同上 | 同上 |
| 回签 | `srm_check_reply_status` | **1.1.4** | `schedule` 先关 |
| 下合同 | `srm_upload_order_attachment` | **1.3.2** | 不设 `dryRun` |
| 查收货 | `srm_stmt_query_receipts` | **1.1.3** | 不设 `dryRun` |
| 生成对账单 | `srm_stmt_generate` | **1.1.0** | 授权前 `dryRun: true` |
| 扫描发票 | `srm_stmt_upload_invoice` | **1.1.2** | 不设 `dryRun` |
| 提交审核 | `srm_stmt_submit_review` | **1.1.5** | 授权前 `dryRun: true` |

---

## 5. C. 你建门户，助手绑后面

### 5.1 你：建门户

生产名称，不要叫「…演练」。密码当场填。

| 字段 | 填什么 |
| --- | --- |
| 名称 | 租户内唯一 |
| 地址 | 正式 SRM |
| 登录账号 / 密码 | 真实账号 |
| 客户编号 / 名称 | SDMS 编码 + 建单抬头 |
| 业务实体 / OU | 我方公司全称 + 公司编号 |
| 归属人 | 实际负责的客服 |

「测试打开」能进 SRM 即可。不要在 SRM 里手点保存/签章/生成/提交。告诉助手**门户准确名称**，绑 Binding 靠这个找。

### 5.2 助手：模板 + Binding

首家至少：扫单、建单、回签、下合同、对账单四条。填交期/签章等正式包好了再补。`config.portalUrl` = 该门户地址。

扫单示例（调度先关）：

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "searches": [
    { "replyStatus": "待签章" }
  ],
  "schedule": {
    "enabled": false,
    "cron": "0 8 * * *",
    "processName": "客户订单",
    "actionName": "扫单"
  }
}
```

回签：`cron` `*/30 * * * *`，`actionName` `回签轮询`，同样先关。之后改 cron/开关只去调度中心。

绑完后重启正式 Task **4520**（建议 Engine 4610）。

---

## 6. 上线当天最短核对

- [ ] Client 连的是正式 Auth/Task
- [ ] 种子关、后继任务开、库已是 head
- [ ] Engine Worker/Runtime 开，凭据 `disabled`
- [ ] Flow 在本环境发布，Binding 不是测试 UUID
- [ ] 门户能测试打开
- [ ] 扫单无 `treatAsPending`
- [ ] 发票目录在 Task 服务器可写
- [ ] 调度仍关；生成/提交仍 `dryRun`（未授权前）
- [ ] 手动扫单：无待签章 = 空列表成功

客服只确认：自己工号能登录、能看见该门户、按 SOP 操作。

---

## 7. 再切真写（必须你口头授权）

| 步 | 做什么 |
| --- | --- |
| 1 | Task `.env` 已是生产 SDMS/ERP，已重启 4520 |
| 2 | 扫单没有样例 `searches` |
| 3 | 空列表扫单成功 |
| 4 | 有真实待签章再扫；缺填交期/签章正式包时单可能停在建 SDMS 之后 |
| 5 | 授权后去掉生成、提交的 `dryRun` |
| 6 | 填交期/签章正式包就绪后再关闸 |
| 7 | 调度中心打开该门户扫单、回签 |

上线成功看 **SRM 状态变了**，不是只看任务 SUCCESS。

---

## 8. 已知缺口

1. 填交期/签章正式包未按真实待签章绑上。演示 1.0.3 禁止绑正式站。
2. Artifact 下载地址必须给 Client 可达主机。
3. 发票在 Task 本机磁盘，生产要备份该目录。
4. 正式环境建议手工迁库，再 `SKIP_AUTO_MIGRATE=1` 启动。

---

## 9. 相关文档

| 要查 | 看 |
| --- | --- |
| 客服每步点什么 | [v4.1 SOP](./AutoTask%20v4.1%20天地伟业正式演练与上线SOP.md) |
| 密码和 SDMS 基址 | [v5.0](./AutoTask%20v5.0%20门户密码.md) |
| 谁能看见门户 | [v5.1](./AutoTask%20v5.1%20权限.md) |
| 调度 | [v5.2](./AutoTask%20v5.2%20调度中心.md) |
| 发票传到 Task | [v5.3](./AutoTask%20v5.3%20对账单发票上传.md) |
