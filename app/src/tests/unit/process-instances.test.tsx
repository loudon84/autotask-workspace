import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  mockList,
  mockGet,
  mockSubmitLineDate,
  mockSign,
  mockArchive,
  mockRetry,
  mockCancel,
} = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockGet: vi.fn(),
  mockSubmitLineDate: vi.fn(),
  mockSign: vi.fn(),
  mockArchive: vi.fn(),
  mockRetry: vi.fn(),
  mockCancel: vi.fn(),
}));

vi.mock("@/services/autotask-api", () => ({
  autotaskApi: {
    processInstances: {
      list: mockList,
      get: mockGet,
      submitLineDate: mockSubmitLineDate,
      sign: mockSign,
      archive: mockArchive,
      retry: mockRetry,
      cancel: mockCancel,
      triggerScan: vi.fn(),
      runSignPollOnce: vi.fn().mockResolvedValue({
        candidateCount: 0,
        createdCount: 0,
      }),
    },
    portalAccounts: {
      list: vi.fn().mockResolvedValue([
        {
          id: "portal-1",
          portalName: "天地伟业技术有限公司",
          businessEntity: "深圳市芯云信息科技有限公司",
          status: "ENABLED",
        },
      ]),
    },
    integrationEndpoints: {
      get: vi.fn().mockResolvedValue({
        sdmsBaseUrl: "http://192.168.99.35:8080",
      }),
    },
  },
}));

vi.mock("@/actions/shell", () => ({
  openExternalLink: vi.fn(),
}));

vi.mock("@/services/endpoint-config", () => ({
  getApiMode: () => "remote",
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) =>
    React.createElement("a", { href: "#" }, children),
}));

import { ProcessesListPage } from "@/features/processes/processes-list";
import { ProcessDetailPage } from "@/features/processes/process-detail";
import { ProcessDatesPage } from "@/features/processes/process-dates";
import type { ProcessInstanceDetail } from "@/types/process-instance";

function makeDetail(overrides: Partial<ProcessInstanceDetail> = {}): ProcessInstanceDetail {
  return {
    id: "inst-1",
    processCode: "srm_customer_order",
    bizKey: "POJS2607130002",
    title: "客户订单处理 - POJS2607130002",
    portalAccountId: "portal-1",
    stage: "SDMS_CREATED",
    status: "ACTIVE",
    lineTotal: 2,
    lineDone: 0,
    createdAt: "2026-08-13T00:00:00Z",
    updatedAt: "2026-08-13T00:00:00Z",
    summary: {
      poNo: "POJS2607130002",
      supplierName: "北京诺德芯信息科技有限公司",
      orderNumber: "10408260800013",
      headerId: "1100983",
    },
    lines: [
      {
        id: "line-10",
        lineNumber: "10",
        materialNumber: "MAT-001",
        itemName: "物料一",
        itemSpecification: "规格A",
        orderQuantity: "100",
        orderQuantityUom: "PCS",
        requestDate: "2026-08-01",
        standardDeliveryDays: "7",
        unitSellingPrice: "1.50",
        remarks: "行备注",
        lineStatus: "PENDING",
      },
      {
        id: "line-20",
        lineNumber: "20",
        materialNumber: "MAT-002",
        itemName: "物料二",
        lineStatus: "WRITTEN",
        expectedDeliveryDate: "2026-08-20",
      },
    ],
    stageHistory: [],
    subTasks: [
      {
        id: "task-1",
        title: "1. 建 SDMS 销售订单 - POJS2607130002",
        taskType: "srm_prepare_erp_order",
        status: "SUCCESS",
        createdAt: "2026-08-13T00:00:00Z",
        updatedAt: "2026-08-13T00:00:00Z",
      },
      {
        id: "task-fill-10-fail",
        title: "2. 填写交货日期(行10) - POJS2607130002",
        taskType: "srm_fill_line_delivery_date",
        status: "FAILED",
        lineNumber: "10",
        createdAt: "2026-08-13T01:00:00Z",
        updatedAt: "2026-08-13T01:00:00Z",
      },
      {
        id: "task-fill-10",
        title: "2. 填写交货日期(行10) - POJS2607130002",
        taskType: "srm_fill_line_delivery_date",
        status: "SUCCESS",
        lineNumber: "10",
        createdAt: "2026-08-13T02:00:00Z",
        updatedAt: "2026-08-13T02:00:00Z",
      },
      {
        id: "task-fill-20",
        title: "2. 填写交货日期(行20) - POJS2607130002",
        taskType: "srm_fill_line_delivery_date",
        status: "SUCCESS",
        lineNumber: "20",
        createdAt: "2026-08-13T02:30:00Z",
        updatedAt: "2026-08-13T02:30:00Z",
      },
    ],
    ...overrides,
  };
}

function renderWithQuery(node: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>
  );
}

describe("ProcessesListPage", () => {
  beforeEach(() => {
    mockList.mockResolvedValue([
      {
        id: "inst-1",
        processCode: "srm_customer_order",
        bizKey: "POJS2607130002",
        title: "客户订单处理 - POJS2607130002",
        portalAccountId: "portal-1",
        stage: "SDMS_CREATED",
        status: "ACTIVE",
        lineTotal: 2,
        lineDone: 1,
        createdAt: "2026-08-13T00:00:00Z",
        updatedAt: "2026-08-13T00:00:00Z",
      },
    ]);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders instance rows with stage and progress", async () => {
    renderWithQuery(<ProcessesListPage />);
    await waitFor(() =>
      expect(screen.getByText("POJS2607130002")).toBeInTheDocument()
    );
    expect(screen.getByText("客户订单流程实例")).toBeInTheDocument();
    expect(screen.getByText("天地伟业技术有限公司")).toBeInTheDocument();
    expect(
      screen.getAllByText("待填写交期").length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("填写交货日期").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1/2")).toBeInTheDocument();
    expect(screen.getByText("进行中")).toBeInTheDocument();
  });

  it("hides statement instances from the customer order list", async () => {
    mockList.mockResolvedValue([
      {
        id: "stmt-1",
        processCode: "srm_tiandi_statement",
        bizKey: "2026-08-18|1151309.12",
        title: "对账单 2026-08-18 / 1151309.12",
        portalAccountId: "portal-1",
        stage: "ARCHIVED",
        status: "COMPLETED",
        lineTotal: 2,
        lineDone: 0,
        createdAt: "2026-08-18T00:00:00Z",
        updatedAt: "2026-08-18T00:00:00Z",
      },
      {
        id: "inst-1",
        processCode: "srm_customer_order",
        bizKey: "POJS2607130002",
        title: "天地伟业-客户订单 - POJS2607130002",
        portalAccountId: "portal-1",
        stage: "SDMS_CREATED",
        status: "ACTIVE",
        lineTotal: 2,
        lineDone: 1,
        createdAt: "2026-08-13T00:00:00Z",
        updatedAt: "2026-08-13T00:00:00Z",
      },
    ]);
    renderWithQuery(<ProcessesListPage />);
    await waitFor(() =>
      expect(screen.getByText("POJS2607130002")).toBeInTheDocument()
    );
    expect(
      screen.queryByText("对账单 2026-08-18 / 1151309.12")
    ).not.toBeInTheDocument();
    expect(screen.queryByText("2026-08-18|1151309.12")).not.toBeInTheDocument();
  });
});

describe("ProcessDetailPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows date-filling button at SDMS_CREATED stage", async () => {
    mockGet.mockResolvedValue(makeDetail());
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(screen.getByText("流程进度")).toBeInTheDocument()
    );
    expect(
      screen.getAllByRole("link", { name: /填写交货日期/ }).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.queryByRole("button", { name: /去签章/ })
    ).not.toBeInTheDocument();
    expect(screen.getByText("客户订单：POJS2607130002")).toBeInTheDocument();
    expect(screen.getByText("客户：天地伟业技术有限公司")).toBeInTheDocument();
    expect(screen.getByText(/交易主体：深圳市芯云信息科技有限公司/)).toBeInTheDocument();
    expect(screen.getByText("1. 建 SDMS 销售订单 - POJS2607130002")).toBeInTheDocument();
    expect(screen.getByText("料品规格")).toBeInTheDocument();
    expect(screen.getByText("单价（元）")).toBeInTheDocument();
    expect(screen.getByText("规格A")).toBeInTheDocument();
    expect(screen.getByText("行备注")).toBeInTheDocument();
    expect(screen.getByText("① 建 SDMS")).toBeInTheDocument();
    expect(screen.getByText("② 填写交货日期")).toBeInTheDocument();
    expect(screen.getByText("行 10")).toBeInTheDocument();
    expect(screen.getByText("历史尝试（1）")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "10408260800013" })).toBeInTheDocument()
    );
  });

  it("shows ERP order as plain text when headerId is missing", async () => {
    mockGet.mockResolvedValue(
      makeDetail({
        summary: {
          poNo: "POJS2607130002",
          orderNumber: "10408260800013",
        },
      })
    );
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(screen.getByText("流程进度")).toBeInTheDocument()
    );
    expect(
      screen.getByText((_, node) => node?.textContent === "ERP 订单：10408260800013")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "10408260800013" })
    ).not.toBeInTheDocument();
  });

  it("shows sign button only at DATES_COMPLETE stage", async () => {
    mockGet.mockResolvedValue(makeDetail({ stage: "DATES_COMPLETE", lineDone: 2 }));
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /去签章/ })).toBeInTheDocument()
    );
    expect(
      screen.queryByRole("link", { name: /^填写交货日期$/ })
    ).not.toBeInTheDocument();
  });

  it("hides archive button at SIGN_REQUESTED stage", async () => {
    mockGet.mockResolvedValue(makeDetail({ stage: "SIGN_REQUESTED" }));
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(screen.getByText("阶段：待回签")).toBeInTheDocument()
    );
    expect(
      screen.queryByRole("button", { name: /手动触发签章合同下载/ })
    ).not.toBeInTheDocument();
    expect(screen.getByText(/双方盖章进行中/)).toBeInTheDocument();
  });

  it("shows archive button at SIGNED stage", async () => {
    mockGet.mockResolvedValue(makeDetail({ stage: "SIGNED" }));
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /手动触发签章合同下载/ })
      ).toBeInTheDocument()
    );
    expect(screen.getByText("阶段：已回签")).toBeInTheDocument();
  });

  it("shows stage badge and blocker when sign failed but instance still active", async () => {
    mockGet.mockResolvedValue(
      makeDetail({
        stage: "DATES_COMPLETE",
        status: "ACTIVE",
        lineDone: 2,
        lastErrorCode: "ORDER_SIGN_STATUS_UNCONFIRMED",
        lastErrorMessage: "Order reply status was not confirmed after sign",
        subTasks: [
          {
            id: "t-sign",
            title: "3. 签章 - POJS2607130002",
            taskType: "srm_sign_order",
            status: "WAITING_HUMAN",
            createdAt: "2026-08-13T10:00:00Z",
            updatedAt: "2026-08-13T10:05:00Z",
          },
        ],
      })
    );
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(screen.getByText("阶段：待签章")).toBeInTheDocument()
    );
    expect(screen.getByText("运行状态：进行中")).toBeInTheDocument();
    expect(screen.getByText("待签章未完成")).toBeInTheDocument();
    expect(
      screen.getByText(/签章后未能确认订单回复状态/)
    ).toBeInTheDocument();
    expect(screen.getByText(/ORDER_SIGN_STATUS_UNCONFIRMED/)).toBeInTheDocument();
  });

  it("shows retry button when failed", async () => {
    mockGet.mockResolvedValue(
      makeDetail({ stage: "FAILED", status: "FAILED", lastErrorMessage: "建单失败" })
    );
    renderWithQuery(<ProcessDetailPage instanceId="inst-1" />);
    await waitFor(() => expect(screen.getByText("重试")).toBeInTheDocument());
    expect(screen.getByText("流程失败")).toBeInTheDocument();
    expect(screen.getAllByText(/建单失败/).length).toBeGreaterThanOrEqual(1);
  });
});

describe("ProcessDatesPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("submits a single line date", async () => {
    mockGet.mockResolvedValue(makeDetail());
    mockSubmitLineDate.mockResolvedValue({});
    renderWithQuery(<ProcessDatesPage instanceId="inst-1" />);

    const input = await screen.findByLabelText("第 10 行预计交货日期");
    await userEvent.type(input, "2026-08-25");
    const rowSaveButtons = screen.getAllByRole("button", { name: /^保存$/ });
    await waitFor(() => expect(rowSaveButtons[0]).toBeEnabled());
    await userEvent.click(rowSaveButtons[0]);

    await waitFor(() =>
      expect(mockSubmitLineDate).toHaveBeenCalledWith({
        instanceId: "inst-1",
        lineNumber: "10",
        expectedDeliveryDate: "2026-08-25",
      })
    );
  });

  it("saves all dirty lines from the header button", async () => {
    mockGet.mockResolvedValue(makeDetail());
    mockSubmitLineDate.mockResolvedValue({});
    renderWithQuery(<ProcessDatesPage instanceId="inst-1" />);

    const line10 = await screen.findByLabelText("第 10 行预计交货日期");
    const line20 = screen.getByLabelText("第 20 行预计交货日期");
    await userEvent.clear(line10);
    await userEvent.type(line10, "2026-09-01");
    await userEvent.clear(line20);
    await userEvent.type(line20, "2026-09-02");

    const saveAll = await screen.findByRole("button", { name: /保存全部/ });
    await waitFor(() => expect(saveAll).toBeEnabled());
    await userEvent.click(saveAll);

    await waitFor(() => expect(mockSubmitLineDate).toHaveBeenCalledTimes(2));
    expect(mockSubmitLineDate).toHaveBeenCalledWith({
      instanceId: "inst-1",
      lineNumber: "10",
      expectedDeliveryDate: "2026-09-01",
    });
    expect(mockSubmitLineDate).toHaveBeenCalledWith({
      instanceId: "inst-1",
      lineNumber: "20",
      expectedDeliveryDate: "2026-09-02",
    });
  });

  it("disables editing when stage is not editable", async () => {
    mockGet.mockResolvedValue(makeDetail({ stage: "SIGN_REQUESTED" }));
    renderWithQuery(<ProcessDatesPage instanceId="inst-1" />);
    await waitFor(() =>
      expect(
        screen.getByText(/当前阶段不允许填写交货日期/)
      ).toBeInTheDocument()
    );
    expect(screen.queryByLabelText("第 10 行预计交货日期")).not.toBeInTheDocument();
  });
});
