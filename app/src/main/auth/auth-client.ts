import {
  type AutoTaskEndpointConfig,
  buildAuthUrl,
} from "@/types/endpoint-config";
import { getEndpointConfig } from "./auth-endpoint-config-store";
import {
  type AuthMeResponse,
  type AuthTokenData,
  type AuthUserResponse,
  isNodeskclawApiEnvelope,
  type StoredAuthSession,
  toStoredSession,
} from "./nodeskclaw-auth-response";
import {
  clearSession,
  getMemorySession,
  loadSession,
  saveSession,
  setMemorySession,
} from "./token-store";

export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

async function authFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (res.status === 204) {
    return undefined as T;
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new AuthError(`Auth request failed: ${res.status}`, res.status);
  }

  if (isNodeskclawApiEnvelope<T>(body)) {
    if (body.code !== 0 || !res.ok) {
      throw new AuthError(
        body.message || `Auth request failed: ${res.status}`,
        res.status
      );
    }
    return body.data;
  }

  if (!res.ok) {
    const fallback = body as { detail?: string; message?: string };
    throw new AuthError(
      fallback.detail ??
        fallback.message ??
        `Auth request failed: ${res.status}`,
      res.status
    );
  }
  return body as T;
}

function getConfig(): AutoTaskEndpointConfig {
  return getEndpointConfig();
}

function resolveAuthUser(
  tokenData: AuthTokenData,
  fallbackUser: AuthUserResponse
): AuthUserResponse {
  if (tokenData.user) {
    return tokenData.user;
  }
  return fallbackUser;
}

function sessionUserToAuthUser(
  user: StoredAuthSession["user"]
): AuthUserResponse {
  return {
    id: user.id,
    email: user.email,
    name: user.displayName,
  };
}

export async function loginWithCredentials(
  account: string,
  password: string
): Promise<StoredAuthSession> {
  const config = getConfig();
  const tokenData = await authFetch<AuthTokenData>(
    buildAuthUrl(config, "/account-login"),
    {
      method: "POST",
      body: JSON.stringify({ account, password }),
    }
  );
  if (!tokenData.user) {
    throw new AuthError("登录响应缺少用户信息", 500);
  }

  const session = toStoredSession(tokenData, tokenData.user);
  await saveSession(session);
  return session;
}

export function fetchMe(accessToken: string): Promise<AuthMeResponse> {
  const config = getConfig();
  return authFetch<AuthMeResponse>(buildAuthUrl(config, "/me"), {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function refreshSession(): Promise<StoredAuthSession | null> {
  const current = getMemorySession() ?? (await loadSession());
  if (!current?.refreshToken) {
    return null;
  }

  const config = getConfig();
  try {
    const tokenData = await authFetch<AuthTokenData>(
      buildAuthUrl(config, "/refresh"),
      {
        method: "POST",
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      }
    );

    const user = await resolveAuthUser(
      tokenData,
      sessionUserToAuthUser(current.user)
    );
    const session = toStoredSession(tokenData, user);
    await saveSession(session);
    return session;
  } catch {
    await clearSession();
    setMemorySession(null);
    return null;
  }
}

export async function logoutSession(): Promise<void> {
  const current = getMemorySession() ?? (await loadSession());
  if (current?.accessToken) {
    const config = getConfig();
    try {
      await authFetch(buildAuthUrl(config, "/logout"), {
        method: "POST",
        headers: { Authorization: `Bearer ${current.accessToken}` },
      });
    } catch {
      // ignore logout errors
    }
  }
  await clearSession();
}

export async function getValidSession(): Promise<StoredAuthSession | null> {
  let session = getMemorySession() ?? (await loadSession());
  if (!session) {
    return null;
  }

  setMemorySession(session);

  const expiresSoon = session.expiresAt - Date.now() < 60_000;
  if (expiresSoon) {
    session = await refreshSession();
  }

  return session;
}

export async function getPublicAuthState() {
  const session = await getValidSession();
  if (!session) {
    return { status: "unauthenticated" as const };
  }

  return {
    status: "authenticated" as const,
    user: session.user,
    organization: session.organization,
  };
}
