import { describe, expect, it, vi } from "vitest";

describe("getApiMode", () => {
  it("defaults to remote when env is unset", async () => {
    vi.stubEnv("VITE_AUTOTASK_API_MODE", "");
    const { getApiMode } = await import("@/types/endpoint-config");
    expect(getApiMode()).toBe("remote");
    vi.unstubAllEnvs();
  });

  it("returns mock when env is mock", async () => {
    vi.stubEnv("VITE_AUTOTASK_API_MODE", "mock");
    const { getApiMode } = await import("@/types/endpoint-config");
    expect(getApiMode()).toBe("mock");
    vi.unstubAllEnvs();
  });

  it("returns remote when env is remote", async () => {
    vi.stubEnv("VITE_AUTOTASK_API_MODE", "remote");
    const { getApiMode } = await import("@/types/endpoint-config");
    expect(getApiMode()).toBe("remote");
    vi.unstubAllEnvs();
  });
});

describe("default endpoint config", () => {
  it("targets the local development services", async () => {
    const {
      buildAuthUrl,
      buildRpaEngineUrl,
      buildTaskUrl,
      defaultAutoTaskEndpointConfig,
    } = await import("@/types/endpoint-config");

    expect(buildAuthUrl(defaultAutoTaskEndpointConfig, "/me")).toBe(
      "http://127.0.0.1:4510/api/v1/auth/me"
    );
    expect(buildTaskUrl(defaultAutoTaskEndpointConfig, "/tasks")).toBe(
      "http://127.0.0.1:4520/api/v1/autotask/tasks"
    );
    expect(buildRpaEngineUrl(defaultAutoTaskEndpointConfig, "/flows")).toBe(
      "http://127.0.0.1:4610/api/v1/flows"
    );
  });

  it("normalizes blank and scheme-less persisted endpoints", async () => {
    const { normalizeAutoTaskEndpointConfig } = await import(
      "@/types/endpoint-config"
    );

    const config = normalizeAutoTaskEndpointConfig({
      authBackendUrl: " ",
      rpaEngineUrl: "localhost:4610/",
      taskBackendUrl: "localhost:4520/",
    });

    expect(config.authBackendUrl).toBe("http://127.0.0.1:4510");
    expect(config.taskBackendUrl).toBe("http://localhost:4520");
    expect(config.rpaEngineUrl).toBe("http://localhost:4610");
    expect(config.authPrefix).toBe("/api/v1/auth");
    expect(config.taskPrefix).toBe("/api/v1/autotask");
  });

    it("builds SDMS OM view URLs from headerId", async () => {
    const { buildSdmsOmViewUrl, buildSdmsCheckViewUrl } = await import(
      "@/types/endpoint-config"
    );
    expect(buildSdmsOmViewUrl("http://192.168.99.35:8080/", "1100983")).toBe(
      "http://192.168.99.35:8080/sdms/om/sdms_om_main/sdmsOmMain.do?method=view&fdId=1100983"
    );
    expect(buildSdmsOmViewUrl("http://example.com", "")).toBeNull();
    expect(buildSdmsCheckViewUrl("http://192.168.99.35:8080/", "36775")).toBe(
      "http://192.168.99.35:8080/sdms/check/sdms_check_cust_headers/sdmsCheckCustHeaders.do?method=view&fdId=36775"
    );
    expect(buildSdmsCheckViewUrl("http://example.com", "")).toBeNull();
  });
});

describe("autotaskApi facade", () => {
  it("exposes domain namespaces", async () => {
    const { autotaskApi } = await import("@/services/autotask-api");
    expect(autotaskApi.dashboard.getSummary).toBeTypeOf("function");
    expect(autotaskApi.tasks.list).toBeTypeOf("function");
    expect(autotaskApi.portalAccounts.list).toBeTypeOf("function");
    expect(autotaskApi.portalAccounts.create).toBeTypeOf("function");
    expect(autotaskApi.portalAccounts.update).toBeTypeOf("function");
    expect(autotaskApi.portalAccounts.delete).toBeTypeOf("function");
    expect(autotaskApi.portalAccounts.testOpen).toBeTypeOf("function");
    expect(autotaskApi.workflowTemplates.delete).toBeTypeOf("function");
    expect(autotaskApi.search).toBeTypeOf("function");
  });
});
