import type { PublicAuthOrganization, PublicAuthUser } from "@/types/auth";

export interface NodeskclawApiEnvelope<T> {
  code: number;
  data: T;
  error_code: string | null;
  message: string;
  message_key: string | null;
}

export interface AuthUserResponse {
  avatar_url?: string | null;
  current_org_id?: string | null;
  email: string;
  id: string;
  is_active?: boolean;
  is_super_admin?: boolean;
  name: string;
  org_role?: string | null;
  organization?: {
    id: string;
    name: string;
  };
  phone?: string | null;
  portal_org_role?: string | null;
  role?: string;
  username?: string;
}
export interface AuthTokenData {
  access_token: string;
  expires_in: number;
  needs_org_setup?: boolean;
  provider?: string | null;
  refresh_token: string;
  token_type: string;
  user?: AuthUserResponse;
}

export type AuthMeResponse = AuthUserResponse;

export interface StoredAuthSession {
  accessToken: string;
  expiresAt: number;
  organization?: PublicAuthOrganization;
  refreshToken: string;
  tokenType: string;
  user: PublicAuthUser;
}

export function mapMeToPublicUser(me: AuthUserResponse): PublicAuthUser {
  return {
    id: me.id,
    email: me.email,
    displayName: me.name ?? me.email,
  };
}

export function mapMeToPublicOrg(
  me: AuthUserResponse
): PublicAuthOrganization | undefined {
  if (me.organization) {
    return {
      id: me.organization.id,
      name: me.organization.name,
    };
  }
  return;
}

export function toStoredSession(
  tokens: Pick<
    AuthTokenData,
    "access_token" | "refresh_token" | "token_type" | "expires_in"
  >,
  me: AuthUserResponse
): StoredAuthSession {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    tokenType: tokens.token_type,
    expiresAt: Date.now() + tokens.expires_in * 1000,
    user: mapMeToPublicUser(me),
    organization: mapMeToPublicOrg(me),
  };
}

export function isNodeskclawApiEnvelope<T>(
  value: unknown
): value is NodeskclawApiEnvelope<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    "data" in value
  );
}

export function unwrapNodeskclawApiEnvelope<T>(body: unknown): T {
  if (isNodeskclawApiEnvelope<T>(body)) {
    if (body.code !== 0) {
      throw new Error(body.message || "Auth request failed");
    }
    return body.data;
  }
  return body as T;
}
