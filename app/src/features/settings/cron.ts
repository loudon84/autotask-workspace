/**
 * 5 段 cron（分 时 日 月 周，本地时间）解析与下次触发计算。
 * 语义与 Task 侧 service/app/services/cron_schedule.py 对齐：
 * 星号、星号/n、a-b、a-b/n、n/m、逗号列表；日/周双受限取 OR；7=周日。
 * 用于调度中心表单的实时"下次触发"预览与保存前校验。
 */

export class CronParseError extends Error {}

interface CronSets {
  minutes: Set<number>;
  hours: Set<number>;
  daysOfMonth: Set<number>;
  months: Set<number>;
  daysOfWeek: Set<number>;
}

export function parseCron(expression: string): CronSets {
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) {
    throw new CronParseError("cron 需为 5 段：分 时 日 月 周");
  }
  return {
    minutes: parseField("分", 0, 59, parts[0]),
    hours: parseField("时", 0, 23, parts[1]),
    daysOfMonth: parseField("日", 1, 31, parts[2]),
    months: parseField("月", 1, 12, parts[3]),
    daysOfWeek: parseField("周", 0, 7, parts[4]),
  };
}

function parseField(label: string, lo: number, hi: number, raw: string): Set<number> {
  const allowed = new Set<number>();
  for (const chunkRaw of raw.split(",")) {
    const chunk = chunkRaw.trim();
    if (!chunk) {
      throw new CronParseError(`cron ${label} 字段含空段`);
    }
    let step = 1;
    let base = chunk;
    const slash = chunk.indexOf("/");
    if (slash !== -1) {
      base = chunk.slice(0, slash);
      step = Number(chunk.slice(slash + 1));
      if (!Number.isInteger(step) || step <= 0) {
        throw new CronParseError(`cron ${label} 步长非法`);
      }
    }
    if (base === "") {
      throw new CronParseError(`cron ${label} 字段非法: ${chunk}`);
    }
    let start: number;
    let end: number;
    let single = false;
    if (base === "*") {
      start = lo;
      end = hi;
    } else if (base.includes("-")) {
      const dash = base.indexOf("-");
      start = Number(base.slice(0, dash));
      end = Number(base.slice(dash + 1));
      if (!Number.isInteger(start) || !Number.isInteger(end)) {
        throw new CronParseError(`cron ${label} 范围非法: ${chunk}`);
      }
    } else {
      start = Number(base);
      if (!Number.isInteger(start)) {
        throw new CronParseError(`cron ${label} 取值非法: ${chunk}`);
      }
      end = start;
      single = true;
    }
    if (start < lo || end > hi || start > end) {
      throw new CronParseError(`cron ${label} 取值越界（${lo}-${hi}）: ${chunk}`);
    }
    // 单数字带步长（如 30/15 → 30,45）扩展到字段上限，与后端一致
    if (single && step !== 1) {
      end = hi;
    }
    for (let v = start; v <= end; v += step) {
      allowed.add(v);
    }
  }
  if (label === "周" && allowed.has(7)) {
    allowed.delete(7);
    allowed.add(0);
  }
  return allowed;
}

/** 返回严格晚于 from 的下一个触发时刻（分钟粒度，本地时间）。 */
export function cronNextAfter(expression: string, from: Date): Date {
  const p = parseCron(expression);
  let t = new Date(
    from.getFullYear(),
    from.getMonth(),
    from.getDate(),
    from.getHours(),
    from.getMinutes() + 1,
    0,
    0
  );
  // JS Date 会自动进位（分钟 60 → 下小时、日 32 → 下月），跳进逻辑因此简化
  for (let i = 0; i < 200_000; i++) {
    if (!p.months.has(t.getMonth() + 1)) {
      t = new Date(t.getFullYear(), t.getMonth() + 1, 1, 0, 0);
      continue;
    }
    if (!dayMatches(p, t)) {
      t = new Date(t.getFullYear(), t.getMonth(), t.getDate() + 1, 0, 0);
      continue;
    }
    if (!p.hours.has(t.getHours())) {
      t = new Date(t.getFullYear(), t.getMonth(), t.getDate(), t.getHours() + 1, 0);
      continue;
    }
    if (!p.minutes.has(t.getMinutes())) {
      t = new Date(t.getFullYear(), t.getMonth(), t.getDate(), t.getHours(), t.getMinutes() + 1);
      continue;
    }
    return t;
  }
  throw new CronParseError("cron 表达式无可触发时刻（如 2 月 30 日）");
}

function dayMatches(p: CronSets, t: Date): boolean {
  const domAny = p.daysOfMonth.size === 31;
  const dowAny = p.daysOfWeek.size === 7;
  const domHit = p.daysOfMonth.has(t.getDate());
  // JS getDay(): 周日=0 … 周六=6，与 cron 编号一致
  const dowHit = p.daysOfWeek.has(t.getDay());
  if (domAny && dowAny) {
    return true;
  }
  if (domAny) {
    return dowHit;
  }
  if (dowAny) {
    return domHit;
  }
  return domHit || dowHit;
}
