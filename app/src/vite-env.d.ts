/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTOTASK_API_MODE?: "mock" | "remote";
  readonly VITE_AUTOTASK_AUTH_BACKEND_URL?: string;
  readonly VITE_AUTOTASK_RPA_ENGINE_URL?: string;
  readonly VITE_AUTOTASK_TASK_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
