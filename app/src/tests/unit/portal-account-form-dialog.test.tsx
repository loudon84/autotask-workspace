import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PortalAccountFormDialog } from "@/features/srm-portals/components/portal-account-form-dialog";
import type { PortalAccount } from "@/types/portal-account";

const { createMutateMock, updateMutateMock } = vi.hoisted(() => ({
  createMutateMock: vi.fn(),
  updateMutateMock: vi.fn(),
}));

vi.mock("@/features/srm-portals/api/use-owner-candidates", () => ({
  useOwnerCandidates: () => ({
    data: [
      { userId: "admin", name: "王冬辉", username: "smc-sz-hr00001" },
      { userId: "zhang", name: "张站", username: "smc-sz-hr15563" },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/modules/auth/AutoTaskAuthProvider", () => ({
  useAuth: () => ({
    authState: {
      status: "authenticated",
      user: { id: "admin", displayName: "admin", email: "admin@example.com" },
    },
  }),
}));

vi.mock("@/features/srm-portals/api/use-portal-account-mutations", () => ({
  useCreatePortalAccount: () => ({
    isPending: false,
    mutate: createMutateMock,
  }),
  useUpdatePortalAccount: () => ({
    isPending: false,
    mutate: updateMutateMock,
  }),
}));

const portal: PortalAccount = {
  id: "portal-1",
  tenantId: "tenant-1",
  entityType: "CUSTOMER",
  erpEntityCode: "C001",
  erpEntityName: "示例客户",
  businessEntity: "深圳市芯云信息科技有限公司",
  ou: "104",
  portalName: "供应商门户",
  portalUrl: "https://supplier.example.com",
  loginAccount: "portal-user",
  clientOpenMode: "webcontents",
  clientSessionPartition: "persist:portal-c001",
  status: "ENABLED",
  ownerUserId: "admin",
  ownerName: "admin",
  createdBy: "admin",
  createdAt: "2026-07-31T00:00:00Z",
  updatedAt: "2026-07-31T00:00:00Z",
};

describe("PortalAccountFormDialog credentialRef", () => {
  beforeEach(() => {
    createMutateMock.mockReset();
    updateMutateMock.mockReset();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("创建 Portal 时提交门户密码", async () => {
    const user = userEvent.setup();
    render(
      <PortalAccountFormDialog mode="create" onOpenChange={vi.fn()} open />
    );

    await user.type(screen.getByLabelText("客户编号 *"), "C001");
    await user.type(screen.getByLabelText("客户名称 *"), "示例客户");
    await user.type(screen.getByLabelText("门户名称 *"), "供应商门户");
    await user.type(
      screen.getByLabelText("门户地址 *"),
      "https://supplier.example.com"
    );
    await user.type(screen.getByLabelText("登录账号 *"), "portal-user");
    await user.type(
      screen.getByLabelText("门户密码 *"),
      "credential-demo"
    );
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(createMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        entityType: "CUSTOMER",
        credentialRef: "credential-demo",
        loginAccount: "portal-user",
      }),
      expect.any(Object)
    );
  });

  it("编辑 Portal 时仅在填写后更新密码", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <PortalAccountFormDialog
        mode="edit"
        onOpenChange={vi.fn()}
        open
        portal={portal}
      />
    );

    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(updateMutateMock.mock.calls[0]?.[0].patch).not.toHaveProperty(
      "credentialRef"
    );

    updateMutateMock.mockReset();
    rerender(
      <PortalAccountFormDialog
        mode="edit"
        onOpenChange={vi.fn()}
        open
        portal={portal}
      />
    );
    await user.type(
      screen.getByLabelText("门户密码"),
      "credential-updated"
    );
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(updateMutateMock.mock.calls[0]?.[0].patch).toMatchObject({
      credentialRef: "credential-updated",
    });
  });

  it("归属人显示姓名和工号，并可以按姓名搜索", async () => {
    const user = userEvent.setup();
    render(
      <PortalAccountFormDialog mode="create" onOpenChange={vi.fn()} open />
    );

    expect(screen.getByRole("button", { name: "归属人" })).toHaveTextContent(
      "王冬辉（smc-sz-hr00001）"
    );

    await user.click(screen.getByRole("button", { name: "归属人" }));
    await user.type(screen.getByPlaceholderText("搜索姓名或工号"), "张站");
    expect(screen.getByText("张站（smc-sz-hr15563）")).toBeInTheDocument();
  });
});
