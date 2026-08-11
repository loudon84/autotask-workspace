import { os } from "@orpc/server";
import {
  getPublicAuthState,
  loginWithCredentials,
  logoutSession,
  refreshSession,
} from "@/main/auth/auth-client";
import { saveEndpointConfig } from "@/main/auth/auth-endpoint-config-store";
import { endpointConfigSchema, loginInputSchema } from "./schemas";

export const getState = os.handler(async () => getPublicAuthState());

export const saveEndpoint = os
  .input(endpointConfigSchema)
  .handler(({ input }) => saveEndpointConfig(input));

export const getEndpointConfig = os.handler(async () => {
  const { getEndpointConfig: getConfig } = await import(
    "@/main/auth/auth-endpoint-config-store"
  );
  return getConfig();
});

export const login = os.input(loginInputSchema).handler(async ({ input }) => {
  await loginWithCredentials(input.account, input.password);
  return getPublicAuthState();
});

export const logout = os.handler(async () => {
  await logoutSession();
  return getPublicAuthState();
});

export const refresh = os.handler(async () => {
  const session = await refreshSession();
  if (!session) {
    return { status: "unauthenticated" as const };
  }
  return getPublicAuthState();
});
