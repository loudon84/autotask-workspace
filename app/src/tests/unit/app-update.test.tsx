import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppUpdateState } from "@/main/app-updater";

const { mockDownload, mockInstall, mockUseAppUpdate } = vi.hoisted(() => ({
  mockDownload: vi.fn(),
  mockInstall: vi.fn(),
  mockUseAppUpdate: vi.fn(),
}));

vi.mock("@/features/app-update/use-app-update", () => ({
  useAppUpdate: mockUseAppUpdate,
}));

import { AppUpdateProvider } from "@/features/app-update/app-update-provider";

function setState(state: AppUpdateState) {
  mockUseAppUpdate.mockReturnValue({
    state,
    download: mockDownload,
    install: mockInstall,
  });
}

beforeEach(() => {
  mockDownload.mockReset();
  mockInstall.mockReset();
  mockUseAppUpdate.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("在线更新弹窗", () => {
  it("idle 时不弹任何窗", () => {
    setState({ status: "idle" });
    render(<AppUpdateProvider />);
    expect(screen.queryByText(/发现新版本/)).not.toBeInTheDocument();
    expect(screen.queryByText(/已就绪/)).not.toBeInTheDocument();
  });

  it("有新版时弹窗，点下载触发 download", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    setState({ status: "available", version: "0.1.2" });
    render(<AppUpdateProvider />);
    await screen.findByText("发现新版本 0.1.2");
    await user.click(screen.getByRole("button", { name: "下载更新" }));
    expect(mockDownload).toHaveBeenCalledTimes(1);
  });

  it("有新版时点稍后，本次不再弹", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    setState({ status: "available", version: "0.1.2" });
    render(<AppUpdateProvider />);
    await screen.findByText("发现新版本 0.1.2");
    await user.click(screen.getByRole("button", { name: "稍后" }));
    await waitFor(() => {
      expect(screen.queryByText("发现新版本 0.1.2")).not.toBeInTheDocument();
    });
    expect(mockDownload).not.toHaveBeenCalled();
  });

  it("下载中显示进度", async () => {
    setState({ status: "downloading", version: "0.1.2", percent: 42 });
    render(<AppUpdateProvider />);
    await screen.findByText("正在下载 0.1.2");
    expect(screen.getByText("42%")).toBeInTheDocument();
  });

  it("下载完成弹安装窗，点现在安装触发 install", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    setState({ status: "downloaded", version: "0.1.2" });
    render(<AppUpdateProvider />);
    await screen.findByText("新版本 0.1.2 已就绪");
    await user.click(screen.getByRole("button", { name: "现在安装" }));
    expect(mockInstall).toHaveBeenCalledTimes(1);
  });
});
