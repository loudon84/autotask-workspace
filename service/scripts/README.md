# service/scripts

联调/运维用的一次性脚本。**不是**对外 API，默认在本机对共享测试库操作，执行前看清备注。

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

## 清空 / 按单号删除流程实例

脚本：`clear_process_instances.py`

硬删客户订单 SOP 联调产生的流程实例及相关任务/Run。  
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
