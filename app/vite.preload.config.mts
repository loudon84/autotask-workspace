import { defineConfig } from "vite";
import { isolateDotEnvDir } from "./vite.env.mts";

export default defineConfig({
  envDir: isolateDotEnvDir(),
  build: {
    sourcemap: true,
  },
});
