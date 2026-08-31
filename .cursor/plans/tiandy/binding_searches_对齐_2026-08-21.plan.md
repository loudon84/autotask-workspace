# Binding 参数落地 Implementation Plan

> 本会话直接执行。不另开演练包。正式红线不变：不点保存/签章/生成/提交审核。

**Goal:** 文档里的 Binding 参数要能真正改行为。换扫单样例 PO 只改门户 Binding JSON，不必改 Flow 源码。

**Architecture:** Task 租约把 Binding `searches` 放进 `config`（与 `dryRun` 同路）。Engine 写入 `ctx.config.searches`。扫单 Flow 只按该列表查询导出；没有第二条就不扫样例单。包内不再默认 `POJS2607170008`。

**Tech Stack:** Task `dispatch_service` / `LeaseCommandConfig`；Engine `RunConfig` / `_safe_config`；Flow `rpa_flow_srm_scan_pending_orders` 1.1.3。

---

## 范围（本次做 / 不做）

### 做

1. Task 派发透传 Binding `searches`。
2. Engine `ctx.config` 带上 `searches`（现 `extra=ignore`，不改字段会丢掉）。
3. 正式扫单 **1.1.3**：读 `searches`；无默认 PO。
4. 正式演练 Binding 真正写入 SOP 那段 JSON，并切 1.1.3。演示扫单仍 1.0.2。
5. 签章 `temp_e2e_backfill_dates` 只给演示门户 URL（含 `192.168.102.247`）；正式站即使误绑演示签章包也不回填。
6. SOP / `正式门户 Flow 演练与上线.md` / `PROJECT_CONTROL` 改成「已写库」，不再写成尚未配置。

### 本次不做（仍记缺口）

- 正式填交期 / 签章包：现有 1.0.3 是演示 `data-rpa`，正式门户未绑。要等正式选择器 + `is_dry_run` 再绑，且必须 `dryRun: true`。
- 生成 / 提交的 `dryRun` 已经通，不改包。
- 税率 / 订单类型等业务默认值。

---

## 文件

| 路径 | 职责 |
| --- | --- |
| `service/app/schemas/dispatch.py` | `LeaseCommandConfig.searches` |
| `service/app/services/dispatch_service.py` | Binding → 租约 config |
| `service/tests/test_rpa_phase5_dispatch.py` | 透传断言 |
| `rpa-engine/src/nodeskclaw_rpa_engine/workers/schemas.py` | `RunConfig.searches` |
| `rpa-engine/src/nodeskclaw_rpa_engine/runtime/engine.py` | `_safe_config` 写入 searches |
| `rpa-engine/tests/test_runtime_engine.py` | ctx.config.searches |
| `rpa-flows/.../1.1.3/*` | 新扫单包 |
| `service/_bind_official_scan_1_1_3.py` | 切版本 + 写 searches |
| `service/app/services/process_instance_service.py` | 演示站才回填交期 |

---

## Binding 契约（扫单）

演练（本次写入正式演练门户）：

```json
{
  "portalUrl": "https://supplier.tiandy.com",
  "searches": [
    { "replyStatus": "待签章" },
    { "poNo": "POJS2607170008", "treatAsPending": true }
  ]
}
```

换单号：只改第二条 `poNo`。上线：删掉第二条。

Flow 规则：

- 有 `searches`：按顺序填表 → 查询 → 导出；第一条有行就停。
- `treatAsPending: true` 才把导出行当成待签章。
- **没有 `searches`、或只有待签章且为空：空列表成功，不再默认任何单号。**
- 兼容：任务 input 显式带非空 `assumedPendingPo` 时，等价于第二条（测试用）。不再包内写死默认 PO。

---

## 验收

1. 单测：Task 快照含 searches；Engine ctx.config 含 searches；Flow 1.1.3 无 `DEFAULT_DRILL_PO`。
2. Client 打开正式演练「扫描待回签」Binding，JSON 里能看到 `searches`。
3. 改第二条 `poNo` 再扫，才会按新单建客户订单（需重启 Task 4520 + Engine 4610）。
4. 演示门户扫单仍 1.0.2。
5. 不点正式 SRM 保存/签章/生成/提交。
