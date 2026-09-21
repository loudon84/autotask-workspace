import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppUpdateState } from "@/main/app-updater";

const { mockCheck, mockDownload, mockInstall, mockUseAppUpdate } = vi.hoisted(
  () => ({
    mockCheck: vi.fn(),
    mockDownload: vi.fn(),
    mockInstall: vi.fn(),
    mockUseAppUpdate: vi.fn(),
  })
);

vi.mock("@/actions/app", () => ({
  getAppVersion: () => Promise.resolve("0.1.23"),
}));

vi.mock("@/features/app-update/use-app-update", () => ({
  useAppUpdate: mockUseAppUpdate,
}));

import { AboutPane } from "@/features/settings/about-pane";

function setState(state: AppUpdateState) {
  mockUseAppUpdate.mockReturnValue({
    state,
    check: mockCheck,
    download: mockDownload,
    downloadAndInstall: mockDownload,
    install: mockInstall,
  });
}

beforeEach(() => {
  mockCheck.mockReset();
  mockDownload.mockReset();
  mockInstall.mockReset();
  mockUseAppUpdate.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("关于与更新", () => {
  it("显示当前版本，点检查更新", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    setState({ status: "idle", supported: true });
    render(<AboutPane />);
    await screen.findByText("0.1.23");
    await user.click(screen.getByRole("button", { name: "检查更新" }));
    expect(mockCheck).toHaveBeenCalledTimes(1);
  });

  it("已是最新时显示说明", async () => {
    setState({ status: "uptodate", supported: true });
    render(<AboutPane />);
    await screen.findByText("已是最新版本");
  });

  it("开发模式不能检查更新", async () => {
    setState({ status: "idle", supported: false });
    render(<AboutPane />);
    await screen.findByText("仅安装版可检查更新。");
    expect(screen.getByRole("button", { name: "检查更新" })).toBeDisabled();
  });
});
