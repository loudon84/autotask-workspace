import { describe, expect, it } from "vitest";
import { BEIJING_TIME_ZONE, formatBeijingDateTime } from "@/utils/date-time";

describe("formatBeijingDateTime", () => {
  it("将 UTC 时间转换为北京时间", () => {
    expect(formatBeijingDateTime("2026-07-30T00:00:00Z")).toBe(
      "2026-07-30 08:00:00"
    );
  });

  it("正确处理跨日转换", () => {
    expect(formatBeijingDateTime("2026-07-29T18:30:15Z")).toBe(
      "2026-07-30 02:30:15"
    );
  });

  it("保留带东八区偏移的北京时间", () => {
    expect(formatBeijingDateTime("2026-07-30T08:00:00+08:00")).toBe(
      "2026-07-30 08:00:00"
    );
  });

  it("将旧 Mock 的无时区时间按北京时间处理", () => {
    expect(formatBeijingDateTime("2026-07-30 09:10:11")).toBe(
      "2026-07-30 09:10:11"
    );
  });

  it("处理空值和非法字符串", () => {
    expect(formatBeijingDateTime(null)).toBe("-");
    expect(formatBeijingDateTime("not-a-date")).toBe("not-a-date");
    expect(BEIJING_TIME_ZONE).toBe("Asia/Shanghai");
  });
});
