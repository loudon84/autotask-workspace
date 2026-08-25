import { describe, expect, it } from "vitest";
import { cronNextAfter, CronParseError } from "@/features/settings/cron";

describe("cron 工具", () => {
  it("每半小时", () => {
    const next = cronNextAfter("*/30 * * * *", new Date(2026, 7, 24, 10, 5));
    expect([next.getHours(), next.getMinutes()]).toEqual([10, 30]);
  });

  it("工作日 8 点跨周末", () => {
    const next = cronNextAfter("0 8 * * 1-5", new Date(2026, 7, 21, 9, 0));
    expect([next.getMonth(), next.getDate(), next.getHours()]).toEqual([
      7, 24, 8,
    ]);
  });

  it("非法表达式抛错", () => {
    expect(() => cronNextAfter("99 * * * *", new Date())).toThrow(
      CronParseError
    );
  });
});
