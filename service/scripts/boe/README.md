# service/scripts/boe

京东方发票箱单 SOP 联调脚本。**不是**对外 API，默认在本机对共享测试库操作，执行前看清备注。与天地伟业脚本（`service/scripts/` 根下）分目录管理。

## 清空 / 按单号删除京东方箱单实例（反复测试用）

脚本：`clear_boe_packing_data.py`

硬删**京东方发票箱单**（`process_code = srm_boe_invoice_packing`）的流程实例及相关任务/Run，便于反复点「立即匹配」重新建单。

会删：

- `process_instances` / `process_line_items` / `process_stage_history`（仅京东方箱单）
- 挂在这些实例上的 `automation_tasks` 及其 `rpa_runs`、`run_events`、`step_runs`、`worker_leases`、`human_actions`、`artifacts`、`task_messages`、`task_successor_jobs`

不会动：

- 天地伟业等其他流程的实例与任务
- WorkflowTemplate / Binding、门户账号、地区映射、调度中心定时器配置

```powershell
cd d:\work_space260811\autotask-workspace\service

# 全量预览 / 全量删除
uv run python scripts\boe\clear_boe_packing_data.py
uv run python scripts\boe\clear_boe_packing_data.py --yes

# 指定交货计划单号预览 / 删除（可多个）
uv run python scripts\boe\clear_boe_packing_data.py 101SJH2026040195
uv run python scripts\boe\clear_boe_packing_data.py --yes 101SJH2026040195
```

### 说明

- 不加 `--yes`：**只打印预览**，不会改库。
- 加 `--yes`：事务内硬删，不可恢复。
- 建议在没有正在跑的相关任务时执行。

### 反复测试循环

1. `clear_boe_packing_data.py --yes` 清空
2. Client「京东方 → 发票箱单」点「立即匹配」（或跑下面的 `verify_boe_timer.py`）
3. 刷新列表看新建实例；要往下走（补全/草稿/提交）需先给门户配 Flow Binding（见下面 `bind_boe_pack_flows.py`）

## 补模板 + 绑京东方 Flow Binding

脚本：`bind_boe_pack_flows.py`

真实租户下补 4 个京东方流程模板（seed JSON 里的 BOE 模板在 seed-tenant-001 下，真实租户没有），并按 `rpa-flows/<flow>/_publish_<ver>.json` 给门户建 ENABLED Binding（enrich / save_draft / submit 1.0.23；delete_draft 1.0.0）。

前置：先在 Engine（4610）侧发布 Flow。只加删草稿、不要重传 1.0.23：

```powershell
cd d:\work_space260811\autotask-workspace\rpa-engine
uv run python scripts\_publish_boe_pack_flows.py --only-delete   # 写 _publish_1.0.0.json
```

然后绑定：

```powershell
cd d:\work_space260811\autotask-workspace\service

uv run python scripts\boe\bind_boe_pack_flows.py                  # 预览（默认只绑演示门户 C000142-01）
uv run python scripts\boe\bind_boe_pack_flows.py --yes            # 实际写入
uv run python scripts\boe\bind_boe_pack_flows.py --yes --all-portals  # 绑所有启用京东方门户
```

幂等：模板/Binding 已存在则跳过；换版本后重跑只会跳过已有 Binding（换版本需另写切换脚本，参考根目录 `_bind_official_*.py`）。

## 验证 boe.pack_match 定时器（等价于调度中心「立即执行」）

脚本：`verify_boe_timer.py`

只读 `timers` 表确认「京东方-匹配交货计划」已登记，然后真实调一次入口（逐租户匹配交货计划，**会真实建单**）。

```powershell
cd d:\work_space260811\autotask-workspace\service
uv run python scripts\boe\verify_boe_timer.py
```

输出 `[OK] 定时器已登记` + `[OK] notify 完成 had_listener=True` 即正常；`[FAIL]` 说明 4520 服务没重启、启动登记未生效。
