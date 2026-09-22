import path from "node:path";
import { defineConfig } from "vite";
import { isolateDotEnvDir } from "./vite.env.mts";

export default defineConfig({
  envDir: isolateDotEnvDir(),
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    sourcemap: true,
  },
});
