import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PortalAccountFormDialog } from "@/features/srm-portals/components/portal-account-form-dialog";
import type { PortalAccount } from "@/types/portal-account";

const { createMutateMock, updateMutateMock } = vi.hoisted(() => ({
  createMutateMock: vi.fn(),
  updateMutateMock: vi.fn(),
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
  portalName: "供应商门户",
  portalUrl: "https://supplier.example.com",
  loginAccount: "portal-user",
  clientOpenMode: "webcontents",
  clientSessionPartition: "persist:portal-c001",
  status: "ENABLED",
  createdBy: "admin",
  createdAt: "2026-07-31T00:00:00Z",
  updatedAt: "2026-07-31T00:00:00Z",
};

describe("PortalAccountFormDialog credentialRef", () => {
  beforeEach(() => {
    createMutateMock.mockReset();
    updateMutateMock.mockReset();
  });

  it("创建 Portal 时提交凭据引用", async () => {
    const user = userEvent.setup();
    render(
      <PortalAccountFormDialog mode="create" onOpenChange={vi.fn()} open />
    );

    await user.type(screen.getByLabelText("客户编码 *"), "C001");
    await user.type(screen.getByLabelText("客户名称 *"), "示例客户");
    await user.type(screen.getByLabelText("门户名称 *"), "供应商门户");
    await user.type(
      screen.getByLabelText("门户地址 *"),
      "https://supplier.example.com"
    );
    await user.type(screen.getByLabelText("登录账号 *"), "portal-user");
    await user.type(
      screen.getByLabelText("凭据引用（credentialRef） *"),
      "credential-demo"
    );
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(createMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        credentialRef: "credential-demo",
        loginAccount: "portal-user",
      }),
      expect.any(Object)
    );
  });

  it("编辑 Portal 时仅在填写后更新凭据引用", async () => {
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
      screen.getByLabelText("凭据引用（credentialRef）"),
      "credential-updated"
    );
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(updateMutateMock.mock.calls[0]?.[0].patch).toMatchObject({
      credentialRef: "credential-updated",
    });
  });
});
