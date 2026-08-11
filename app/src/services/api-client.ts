import { toast } from "sonner";
import { refreshAuth } from "@/actions/auth";
import { ApiClientError, requestAutotaskApi } from "@/actions/autotask-api";

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export async function apiRequest<T>(
  input: Parameters<typeof requestAutotaskApi<T>>[0]
): Promise<T> {
  try {
    return await requestAutotaskApi<T>(input);
  } catch (err) {
    const status = err instanceof ApiClientError ? err.status : 500;
    const message = err instanceof Error ? err.message : "请求失败";

    if (status === 401) {
      try {
        const state = await refreshAuth();
        if (state.status === "authenticated") {
          return await requestAutotaskApi<T>(input);
        }
      } catch {
        // fall through
      }
      onUnauthorized?.();
      toast.error("登录已过期，请重新登录");
      throw err;
    }

    if (status === 403) {
      toast.error("权限不足");
      throw err;
    }

    if (status >= 500) {
      toast.error(message || "服务器错误");
      throw err;
    }

    throw err;
  }
}
