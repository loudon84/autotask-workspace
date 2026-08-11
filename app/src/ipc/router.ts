import { app } from "./app";
import { auth } from "./auth";
import { autotaskApi } from "./autotask-api";
import { rpaEngine } from "./rpa-engine";
import { shell } from "./shell";
import { theme } from "./theme";
import { webWorkspace } from "./web-workspace";
import { window } from "./window";

export const router = {
  theme,
  window,
  app,
  shell,
  webWorkspace,
  auth,
  autotaskApi,
  rpaEngine,
};
