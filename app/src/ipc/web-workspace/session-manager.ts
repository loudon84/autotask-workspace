import { session } from "electron";

const BLOCKED_PROTOCOLS = ["file:", "javascript:", "data:"];

export function validateUrl(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("无效的 URL");
  }

  if (BLOCKED_PROTOCOLS.includes(parsed.protocol)) {
    throw new Error(`禁止打开协议: ${parsed.protocol}`);
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`不支持的协议: ${parsed.protocol}`);
  }
}

export function resolvePartition(partition?: string): string {
  return partition ?? "persist:autotask-global";
}

export function getSession(partition: string) {
  return session.fromPartition(partition, { cache: true });
}

export async function clearSession(partition: string): Promise<void> {
  const ses = getSession(partition);
  await ses.clearStorageData();
  await ses.clearCache();
}

export async function clearAllWebSessions(): Promise<void> {
  const partitions = [
    "persist:autotask-global",
    ...Array.from({ length: 20 }, (_, i) => `persist:srm:portal_${String(i + 1).padStart(3, "0")}`),
  ];
  await Promise.all(partitions.map((p) => clearSession(p).catch(() => undefined)));
}
