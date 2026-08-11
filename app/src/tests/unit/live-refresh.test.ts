import { describe, expect, it } from "vitest";
import {
  getRemoteRefreshInterval,
  LIVE_LOG_REFRESH_INTERVAL_MS,
  LIVE_STATUS_REFRESH_INTERVAL_MS,
} from "@/services/live-refresh";

describe("getRemoteRefreshInterval", () => {
  it("远程模式按两秒刷新任务状态", () => {
    expect(getRemoteRefreshInterval(true)).toBe(
      LIVE_STATUS_REFRESH_INTERVAL_MS
    );
  });

  it("Mock 模式不启动轮询", () => {
    expect(getRemoteRefreshInterval(false)).toBe(false);
  });

  it("运行详情和日志可以使用一秒刷新间隔", () => {
    expect(getRemoteRefreshInterval(true, LIVE_LOG_REFRESH_INTERVAL_MS)).toBe(
      1000
    );
  });
});
