import type { StoredAuthSession } from "./nodeskclaw-auth-response";

export function buildAuthHeaders(
  session: StoredAuthSession
): Record<string, string> {
  const tokenType = session.tokenType || "Bearer";
  return {
    Authorization: `${tokenType} ${session.accessToken}`,
    "Content-Type": "application/json",
  };
}
