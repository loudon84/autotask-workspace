import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/business/status-badge";

describe("StatusBadge", () => {
  it("普通 DRAFT 状态保持显示为草稿", () => {
    render(<StatusBadge status="DRAFT" />);

    expect(screen.getByText("草稿")).toBeInTheDocument();
  });

  it("允许交货日期任务将 DRAFT 显示为待填写", () => {
    render(<StatusBadge labelOverride="待填写" status="DRAFT" />);

    expect(screen.getByText("待填写")).toBeInTheDocument();
    expect(screen.queryByText("草稿")).not.toBeInTheDocument();
  });
});
