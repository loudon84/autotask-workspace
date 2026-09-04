import { app } from "./app";
import { appUpdate } from "./app-update";
import { auth } from "./auth";
import { autotaskApi } from "./autotask-api";
import { rpaEngine } from "./rpa-engine";
import { shell } from "./shell";
import { theme } from "./theme";
import { webWorkspace } from "./web-workspace";
import { window } from "./window";

// @lat: [[client#Process Layers]]
export const router = {
  theme,
  window,
  app,
  appUpdate,
  shell,
  webWorkspace,
  auth,
  autotaskApi,
  rpaEngine,
};
