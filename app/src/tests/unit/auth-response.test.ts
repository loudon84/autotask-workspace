import { describe, expect, it } from "vitest";

import type {
  AuthMeResponse,
  AuthTokenData,
} from "@/main/auth/nodeskclaw-auth-response";
import { unwrapApiResponse } from "@/types/api-response";

describe("unwrapApiResponse", () => {
  it("unwraps the backend success envelope", () => {
    const tokens = unwrapApiResponse<AuthTokenData>({
      code: 0,
      data: {
        access_token: "access-token",
        expires_in: 3600,
        refresh_token: "refresh-token",
        token_type: "Bearer",
      },
      error_code: null,
      message: "success",
    });

    expect(tokens.access_token).toBe("access-token");
  });

  it("keeps the legacy top-level response compatible", () => {
    const me: AuthMeResponse = {
      email: "local@example.com",
      id: "local-user",
      name: "Local User",
    };

    expect(unwrapApiResponse<AuthMeResponse>(me)).toBe(me);
  });
});
