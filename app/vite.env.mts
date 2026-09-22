import fs from "node:fs";
import path from "node:path";

const APP_ROOT = import.meta.dirname;
const ISOLATED_DIR = path.join(APP_ROOT, ".vite-env");

/** Vite 默认还会读 .env.development / .env.production。隔离后只喂一份 .env。 */
export function isolateDotEnvDir(): string {
  fs.mkdirSync(ISOLATED_DIR, { recursive: true });
  const src = path.join(APP_ROOT, ".env");
  const dest = path.join(ISOLATED_DIR, ".env");
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest);
  } else if (fs.existsSync(dest)) {
    fs.unlinkSync(dest);
  }
  for (const extra of [
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.development.local",
    ".env.production.local",
  ]) {
    const extraPath = path.join(ISOLATED_DIR, extra);
    if (fs.existsSync(extraPath)) {
      fs.unlinkSync(extraPath);
    }
  }
  return ISOLATED_DIR;
}
