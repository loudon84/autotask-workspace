import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/modules/auth/AutoTaskAuthProvider";
import { autotaskApi } from "@/services/autotask-api";
import { getApiMode } from "@/services/endpoint-config";
import { queryKeys } from "@/services/query-keys";

function resolveAuthStatus(
  status: ReturnType<typeof useAuth>["authState"]["status"]
): "logged-in" | "expired" | "loading" {
  if (status === "authenticated") {
    return "logged-in";
  }
  if (status === "unauthenticated") {
    return "expired";
  }
  return "loading";
}

function resolveTaskApiStatus(
  isRemote: boolean,
  authStatus: ReturnType<typeof useAuth>["authState"]["status"],
  isError: boolean,
  apiConnected?: boolean
): "mock" | "disconnected" | "connected" | "checking" {
  if (!isRemote) {
    return "mock";
  }
  if (authStatus !== "authenticated") {
    return "disconnected";
  }
  if (isError) {
    return "disconnected";
  }
  if (apiConnected) {
    return "connected";
  }
  return "checking";
}

export function useBackendStatus() {
  const { authState } = useAuth();
  const isRemote = getApiMode() === "remote";

  const { data: apiConnected, isError } = useQuery({
    queryKey: queryKeys.backendStatus.all,
    queryFn: async () => {
      await autotaskApi.dashboard.getSummary();
      return true;
    },
    enabled: isRemote && authState.status === "authenticated",
    refetchInterval: 30_000,
    retry: false,
  });

  const authStatus = resolveAuthStatus(authState.status);
  const taskApiStatus = resolveTaskApiStatus(
    isRemote,
    authState.status,
    isError,
    apiConnected
  );

  return { authStatus, taskApiStatus, isRemote };
}
