import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockList, mockGet, mockPatch, mockListTasks } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockGet: vi.fn(),
  mockPatch: vi.fn(),
  mockListTasks: vi.fn(),
}));

vi.mock("@/services/autotask-api", () => ({
  autotaskApi: {
    schedulerJobs: {
      list: mockList,
      get: mockGet,
      patch: mockPatch,
      listTasks: mockListTasks,
    },
  },
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
import type { SchedulerJob } from "@/features/schedulers/types";

const enabledJob: SchedulerJob = {
  id: "job-1",
  bindingId: "b1",
  portalAccountId: "p1",
  portalName: "天地伟业",
  name: "天地伟业-客户订单-扫单",
  cron: "0 8 * * *",
  enabled: true,
  nextRunAt: "2026-08-25T00:00:00+08:00",
};

const disabledJob: SchedulerJob = {
  ...enabledJob,
  id: "job-2",
  name: "天地伟业-客户订单-回签轮询",
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
  mockListTasks.mockReset();
  mockList.mockResolvedValue([enabledJob, disabledJob]);
  mockGet.mockResolvedValue(enabledJob);
  mockPatch.mockResolvedValue({ ...enabledJob, cron: "0 9 * * *" });
  mockListTasks.mockResolvedValue({
    items: [],
    total: 0,
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
    await screen.findByText("天地伟业-客户订单-扫单");
    expect(screen.queryByRole("button", { name: /新建/ })).not.toBeInTheDocument();
  });

  it("筛选启用只请求 enabled=true", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulersListPage />);
    await screen.findByText("天地伟业-客户订单-扫单");
    expect(mockList).toHaveBeenCalledWith(undefined);

    mockList.mockResolvedValueOnce([enabledJob]);
    await user.click(screen.getByRole("combobox", { name: "按启用状态筛选" }));
    await user.click(await screen.findByRole("option", { name: "启用" }));

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(true);
    });
  });
});

describe("调度任务详情", () => {
  it("改 cron 后保存会 PATCH", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithClient(<SchedulerJobDetailPage jobId="job-1" />);
    const input = await screen.findByLabelText("cron");
    expect(
      screen.getByText(/没有候选时列表为空，不代表定时器没跑/)
    ).toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "0 9 * * *");
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("job-1", {
        enabled: true,
        cron: "0 9 * * *",
      });
    });
  });
});
