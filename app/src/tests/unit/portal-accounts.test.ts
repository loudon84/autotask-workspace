import { describe, expect, it } from "vitest";
import {
  mapPortalAccount,
  mapPortalAccountList,
  unwrapApiResponse,
} from "@/services/dto-mappers";

describe("mapPortalAccount", () => {
  it("maps legacy mock fields to PortalAccount", () => {
    const result = mapPortalAccount({
      id: "portal_001",
      customerName: "客户A",
      name: "客户A SRM",
      url: "https://example.com",
      status: "enabled",
      clientOpenMode: "webcontents",
      clientSessionPartition: "persist:test",
      createdAt: "2026-01-01",
      updatedAt: "2026-01-02",
    });

    expect(result.erpEntityName).toBe("客户A");
    expect(result.portalName).toBe("客户A SRM");
    expect(result.portalUrl).toBe("https://example.com");
    expect(result.status).toBe("ENABLED");
  });

  it("maps backend PortalAccount fields directly", () => {
    const result = mapPortalAccount({
      id: "p1",
      tenant_id: "t1",
      entity_type: "CUSTOMER",
      erp_entity_code: "CUST-001",
      erp_entity_name: "示例客户",
      portal_name: "生产门户",
      portal_url: "https://portal.example.com",
      login_account: "buyer@example.com",
      client_open_mode: "system_browser",
      client_session_partition: "persist:portal-cust-001",
      status: "DISABLED",
      created_by: "admin",
      created_at: "2026-01-01",
      updated_at: "2026-01-02",
    });

    expect(result.erpEntityCode).toBe("CUST-001");
    expect(result.portalName).toBe("生产门户");
    expect(result.status).toBe("DISABLED");
    expect(result.clientOpenMode).toBe("system_browser");
  });
});

describe("mapPortalAccountList", () => {
  it("unwraps envelope and maps list", () => {
    const result = mapPortalAccountList({
      code: 0,
      message: "success",
      data: [
        {
          id: "p1",
          portal_name: "Portal 1",
          portal_url: "https://a.com",
          status: "ENABLED",
        },
      ],
    });

    expect(result).toHaveLength(1);
    expect(result[0]?.portalName).toBe("Portal 1");
  });
});

describe("unwrapApiResponse", () => {
  it("returns data when code is 0", () => {
    const result = unwrapApiResponse({
      code: 0,
      message: "success",
      data: { id: "1" },
    });
    expect(result).toEqual({ id: "1" });
  });

  it("throws when code is not 0", () => {
    expect(() =>
      unwrapApiResponse({
        code: 1,
        message: "业务错误",
        data: null,
      })
    ).toThrow("业务错误");
  });
});
