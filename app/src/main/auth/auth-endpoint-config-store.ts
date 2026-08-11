import fs from "node:fs";
import path from "node:path";
import { app } from "electron";
import {
  type AutoTaskEndpointConfig,
  defaultAutoTaskEndpointConfig,
  normalizeAutoTaskEndpointConfig,
} from "@/types/endpoint-config";

const CONFIG_FILE = "autotask-endpoint-config.json";

let cachedConfig: AutoTaskEndpointConfig | null = null;

function getConfigPath(): string {
  return path.join(app.getPath("userData"), CONFIG_FILE);
}

export function getEndpointConfig(): AutoTaskEndpointConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  try {
    const filePath = getConfigPath();
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf-8");
      cachedConfig = normalizeAutoTaskEndpointConfig(JSON.parse(raw));
      fs.writeFileSync(
        filePath,
        JSON.stringify(cachedConfig, null, 2),
        "utf-8"
      );
      return cachedConfig;
    }
  } catch {
    // 配置文件不可用时回退到本地默认值。
  }

  cachedConfig = { ...defaultAutoTaskEndpointConfig };
  return cachedConfig;
}

export function saveEndpointConfig(
  config: AutoTaskEndpointConfig
): AutoTaskEndpointConfig {
  cachedConfig = normalizeAutoTaskEndpointConfig(config);
  const filePath = getConfigPath();
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(cachedConfig, null, 2), "utf-8");
  return cachedConfig;
}
