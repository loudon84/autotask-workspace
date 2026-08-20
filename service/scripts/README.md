# service/scripts

联调/运维用的一次性脚本。**不是**对外 API，默认在本机对共享测试库操作，执行前看清备注。

## 天地伟业 v4.0 演练种子（当成待签章扫入）

脚本：`seed_tiandi_drill.py`

把正式站样例 PO（默认 `POJS2607170008`）当成扫单结果，创建客户订单并排队「建 SDMS 销售订单」。不调 SRM。

```powershell
cd d:\work_space260811\autotask-workspace\service

# 预览
.\.venv\Scripts\python.exe scripts\seed_tiandi_drill.py

# 写库
.\.venv\Scripts\python.exe scripts\seed_tiandi_drill.py --yes POJS2607170008
```

## 刷回待回签（复测回签轮询）

脚本：`reset_to_sign_requested.py`

把指定采购订单号的流程实例改成 `SIGN_REQUESTED` + `ACTIVE`，并软删会挡住回签探测的归档任务。

```powershell
cd d:\work_space260811\autotask-workspace\service

# 预览
.\.venv\Scripts\python.exe scripts\reset_to_sign_requested.py POJS2607240005

# 执行（可多个单号）
.\.venv\Scripts\python.exe scripts\reset_to_sign_requested.py --yes POJS2607240005 POJS2607240006
```

## 清空 / 按单号删除流程实例（客户订单）

脚本：`clear_process_instances.py`

硬删**客户订单** SOP 联调产生的流程实例及相关任务/Run。  
会删全部 `process_instances`（不传单号时），**不要**用它清对账单。  
不动：WorkflowTemplate / Binding、门户账号、Engine Flow Registry、MinIO 包。

```powershell
cd d:\work_space260811\autotask-workspace\service

# 全量预览 / 全量删除
.\.venv\Scripts\python.exe scripts\clear_process_instances.py
.\.venv\Scripts\python.exe scripts\clear_process_instances.py --yes

# 指定单号预览 / 删除（可多个）
.\.venv\Scripts\python.exe scripts\clear_process_instances.py POJS2607240005
.\.venv\Scripts\python.exe scripts\clear_process_instances.py --yes POJS2607240005 POJS2607240006
```

### 说明

- 不加 `--yes`：**只打印预览**，不会改库。
- 加 `--yes`：事务内执行（清空为硬删，不可恢复）。
- 建议在没有正在跑的相关任务时执行；若 Worker 正跑，个别 Run 可能报错，一般可忽略。

### 清空会删到的表（概要）

- `process_instances` / `process_line_items` / `process_stage_history`
- 挂了 `process_instance_id` 的 `automation_tasks` 及其 `rpa_runs`、事件、步骤、制品、租约、人工动作、后继作业等

## 清空对账单 SOP

脚本：`clear_statement_bills.py`

硬删**天地伟业对账单**（`process_code = srm_tiandi_statement`）的账单、流程实例及相关任务/Run。  
全量时也会清填单页产生的、未挂实例的查询收货任务。  
**不影响客户订单。**

```powershell
cd d:\work_space260811\autotask-workspace\service

# 全量预览 / 全量删除
.\.venv\Scripts\python.exe scripts\clear_statement_bills.py
.\.venv\Scripts\python.exe scripts\clear_statement_bills.py --yes

# 指定对账单 id 预览 / 删除（可多个）
.\.venv\Scripts\python.exe scripts\clear_statement_bills.py <bill-id>
.\.venv\Scripts\python.exe scripts\clear_statement_bills.py --yes <bill-id>
```

对账单 id 在 Client 详情 URL：`/process-instances/statements/$billId`。

### 说明

- 不加 `--yes`：**只打印预览**，不会改库。
- 加 `--yes`：事务内硬删，不可恢复。
- 建议在没有正在跑的对账单任务时执行。

## v5.0 上线切换（环境基址，不是 Binding）

外部系统**域名和 OAuth** 只放 Task `.env`。换测试/正式改这一处，重启 Task 4520。不要把 URL 写进每个 Binding JSON，也不要在 Client 登录页配。

- `SMC_API_BASE_URL`：公司内部接口平台（对账单查询等 SQL→JSON）
- `SDMS_BASE_URL`：SDMS 网页主机（Client 跳转销售订单/对账单）

```
SMC_API_BASE_URL=http://api.qywx.smart-core.com.cn
SDMS_BASE_URL=http://192.168.99.35:8080
ERP_BASE_URL=http://192.168.99.111:8080
OA_BASE_URL=
ERP_CLIENT_ID=
ERP_CLIENT_SECRET=
SDMS_ATTACHMENT_API_BASE_URL=http://api.doc.uat.smart-core.com.hk
```

正式环境把上面主机换成正式地址即可。密钥不要写进 Git、不要写进 Binding。

同时：

1. 每个门户编辑里重填一次 SRM 密码（旧 `credential_ref` 是编号，不能登录）。
2. 发布并切换建单 Flow **1.2.8**、传合同 **1.2.3**。
3. Engine `.env`：`CREDENTIAL_RESOLVER_MODE=disabled`，去掉 `MOCK_SRM_*` 凭据项。

