import { describe, expect, it } from "vitest";
import { formatOwnerLabel } from "@/features/srm-portals/owner-label";

describe("formatOwnerLabel", () => {
  it("姓名加括号工号", () => {
    expect(formatOwnerLabel("张站", "smc-sz-hr15563")).toBe(
      "张站（smc-sz-hr15563）"
    );
  });

  it("缺一则只显示有的", () => {
    expect(formatOwnerLabel("张站", "")).toBe("张站");
    expect(formatOwnerLabel("", "smc-sz-hr15563")).toBe("smc-sz-hr15563");
  });
});
