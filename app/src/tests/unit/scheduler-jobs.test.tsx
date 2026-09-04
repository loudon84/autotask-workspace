import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockList, mockGet, mockPatch, mockListRuns, mockRunNow } = vi.hoisted(
  () => ({
    mockList: vi.fn(),
    mockGet: vi.fn(),
    mockPatch: vi.fn(),
    mockListRuns: vi.fn(),
    mockRunNow: vi.fn(),
  })
);

vi.mock("@/services/autotask-api", () => ({
  autotaskApi: {
    timers: {
      list: mockList,
      get: mockGet,
      patch: mockPatch,
      listRuns: mockListRuns,
      runNow: mockRunNow,
    },
  },
}));

const { mockMutateSchedulerSettings } = vi.hoisted(() => ({
  mockMutateSchedulerSettings: vi.fn(),
}));

vi.mock("@/features/settings/api/use-scheduler-settings", () => ({
  useSchedulerSettings: () => ({
    data: {
      signPoll: { enabled: false, cron: "*/30 * * * *" },
      scan: { enabled: false, cron: "0 8 * * *" },
      boePack: { enabled: false, cron: "0 7 * * *" },
      nextRunAt: { signPoll: null, scan: null, boePack: null },
    },
    isLoading: false,
    isError: false,
  }),
  useUpdateSchedulerSettings: () => ({
    mutate: mockMutateSchedulerSettings,
    isPending: false,
  }),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) =>
    React.createElement("a", { href: "#" }, children),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { SchedulersListPage } from "@/features/schedulers/schedulers-list";
import { SchedulerJobDetailPage } from "@/features/schedulers/scheduler-job-detail";
import type { Timer } from "@/features/schedulers/types";

const enabledJob: Timer = {
  id: "job-1",
  name: "打印当前时间",
  cron: "0 8 * * *",
  enabled: true,
  nextRunAt: "2026-08-25T00:00:00+08:00",
};

const disabledJob: Timer = {
  ...enabledJob,
  id: "job-2",
  name: "另一条定时器",
  cron: "*/30 * * * *",
  enabled: false,
  nextRunAt: null,
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
  mockList.mockReset();
  mockGet.mockReset();
  mockPatch.mockReset();

  mockListRuns.mockReset();
  mockRunNow.mockReset();
  mockList.mockResolvedValue([enabledJob, disabledJob]);
  mockGet.mockResolvedValue(enabledJob);
  mockPatch.mockResolvedValue({ ...enabledJob, cron: "0 9 * * *" });
  mockRunNow.mockResolvedValue({ status: "SUCCESS", message: "已执行成功" });
  mockListRuns.mockResolvedValue({
    items: [
      {
        id: "run-1",
        status: "SUCCESS",
        triggeredAt: "2026-08-24T08:00:00+08:00",
        finishedAt: "2026-08-24T08:00:03+08:00",
        error: null,
      },
    ],
    total: 1,
    page: 1,
    pageSize: 20,
  });
});

afterEach(() => {
  cleanup();
});

describe("调度中心列表", () => {
  it("没有新建按钮", async () => {
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("打印当前时间");
    expect(screen.queryByRole("button", { name: /新建/ })).not.toBeInTheDocument();
  });


  it("显示京东方匹配交货计划租户级定时器", async () => {
    renderWithClient(<SchedulersListPage />);
    expect(await screen.findByText("京东方匹配交货计划")).toBeInTheDocument();
    expect(screen.getByLabelText("启用")).toBeInTheDocument();
    expect(screen.getByLabelText("cron")).toBeInTheDocument();
  });

  it("保存京东方定时器只提交 boePack", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("京东方匹配交货计划");
    await user.click(screen.getByLabelText("启用"));
    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(mockMutateSchedulerSettings).toHaveBeenCalledWith(
      { boePack: { enabled: true, cron: "0 7 * * *" } },
      expect.any(Object)
    );
  it("没有门户列", async () => {
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("打印当前时间");
    expect(screen.queryByText("门户")).not.toBeInTheDocument();
  });

  it("筛选启用只请求 enabled=true", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("打印当前时间");
    expect(mockList).toHaveBeenCalledWith(undefined);

    mockList.mockResolvedValueOnce([enabledJob]);
    await user.click(screen.getByRole("combobox", { name: "按启用状态筛选" }));
    await user.click(await screen.findByRole("option", { name: "启用" }));

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(true);
    });
  });

  it("每行都有立即执行，停用的任务也能点", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("另一条定时器");
    const buttons = screen.getAllByRole("button", { name: "立即执行" });
    expect(buttons).toHaveLength(2);
    // 第二个是停用的任务，按钮不应被禁用
    expect(buttons[1]).not.toBeDisabled();

    await user.click(buttons[1]);
    await waitFor(() => {
      expect(mockRunNow).toHaveBeenCalledWith("job-2");
    });
  });
});

describe("定时器详情", () => {
  it("没有 Binding 任务列表", async () => {
    renderWithClient(<SchedulerJobDetailPage jobId="job-1" />);
    await screen.findByLabelText("cron");
    expect(screen.queryByText("执行任务")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/没有候选时列表为空/)
    ).not.toBeInTheDocument();
  });

  it("显示执行记录", async () => {
    renderWithClient(<SchedulerJobDetailPage jobId="job-1" />);
    await screen.findByText("执行记录");
    expect(screen.getByText("触发时间")).toBeInTheDocument();
    expect(screen.getByText("结束时间")).toBeInTheDocument();
    expect(await screen.findByText("成功")).toBeInTheDocument();
  });

  it("改 cron 后保存会 PATCH", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulerJobDetailPage jobId="job-1" />);
    const input = await screen.findByLabelText("cron");
    await user.clear(input);
    await user.type(input, "0 9 * * *");
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("job-1", {
        name: "打印当前时间",
        enabled: true,
        cron: "0 9 * * *",
      });
    });
  });

  it("点立即执行会触发 runNow 并刷新执行记录", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulerJobDetailPage jobId="job-1" />);
    await screen.findByText("执行记录");
    await user.click(screen.getByRole("button", { name: "立即执行" }));
    await waitFor(() => {
      expect(mockRunNow).toHaveBeenCalledWith("job-1");
    });
  });
});
