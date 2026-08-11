import fs from "node:fs/promises";
import path from "node:path";
import { app, safeStorage } from "electron";
import type { StoredAuthSession } from "./nodeskclaw-auth-response";

export type { StoredAuthSession } from "./nodeskclaw-auth-response";

const TOKEN_FILE = "autotask-auth-session.bin";

let memorySession: StoredAuthSession | null = null;

function getTokenFilePath(): string {
  return path.join(app.getPath("userData"), TOKEN_FILE);
}

export async function loadSession(): Promise<StoredAuthSession | null> {
  if (memorySession) {
    return memorySession;
  }

  if (!safeStorage.isEncryptionAvailable()) {
    return null;
  }

  try {
    const encrypted = await fs.readFile(getTokenFilePath());
    const decrypted = safeStorage.decryptString(encrypted);
    const session = JSON.parse(decrypted) as StoredAuthSession;
    memorySession = session;
    return session;
  } catch {
    return null;
  }
}

export async function saveSession(session: StoredAuthSession): Promise<void> {
  memorySession = session;

  if (!safeStorage.isEncryptionAvailable()) {
    return;
  }

  const filePath = getTokenFilePath();
  const encrypted = safeStorage.encryptString(JSON.stringify(session));

  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, encrypted);
}

export async function clearSession(): Promise<void> {
  memorySession = null;

  try {
    await fs.rm(getTokenFilePath(), { force: true });
  } catch {
    // ignore
  }
}

export async function hasSession(): Promise<boolean> {
  const session = await loadSession();
  return Boolean(session?.accessToken);
}

export function getMemorySession(): StoredAuthSession | null {
  return memorySession;
}

export function setMemorySession(session: StoredAuthSession | null): void {
  memorySession = session;
}
