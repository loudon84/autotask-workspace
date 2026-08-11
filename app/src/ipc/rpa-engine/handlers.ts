import fs from "node:fs/promises";
import path from "node:path";
import { ORPCError, os } from "@orpc/server";
import { dialog } from "electron";
import {
  listFlows as listEngineFlows,
  publishFlowVersion as publishEngineFlowVersion,
  RpaEngineApiError,
  uploadFlowPackage as uploadEngineFlowPackage,
  validateFlowVersion as validateEngineFlowVersion,
} from "@/main/rpa-engine/rpa-engine-client";
import {
  listFlowsSchema,
  publishFlowVersionSchema,
  uploadFlowPackageSchema,
  validateFlowVersionSchema,
} from "./schemas";

const MAX_CLIENT_PACKAGE_BYTES = 64 * 1024 * 1024;

function raiseEngineError(error: unknown): never {
  if (error instanceof RpaEngineApiError) {
    throw new ORPCError("RPA_ENGINE_API_ERROR", {
      data: error.body,
      message: error.message,
      status: error.status,
    });
  }
  throw error;
}

export const listFlows = os
  .input(listFlowsSchema)
  .handler(async ({ input }) => {
    try {
      return await listEngineFlows(input.scope);
    } catch (error) {
      return raiseEngineError(error);
    }
  });

export const uploadFlowPackage = os
  .input(uploadFlowPackageSchema)
  .handler(async ({ input }) => {
    const selection = await dialog.showOpenDialog({
      filters: [{ extensions: ["zip"], name: "AutoTask Flow ZIP" }],
      properties: ["openFile", "dontAddToRecent"],
      title: "选择要上传的 Flow 包",
    });
    if (selection.canceled || selection.filePaths.length === 0) {
      return { cancelled: true as const };
    }

    const filePath = selection.filePaths[0];
    const fileName = path.basename(filePath);
    if (path.extname(fileName).toLowerCase() !== ".zip") {
      throw new ORPCError("BAD_REQUEST", {
        message: "只能上传 ZIP 格式的 Flow 包",
        status: 400,
      });
    }

    const stat = await fs.stat(filePath);
    if (stat.size <= 0) {
      throw new ORPCError("BAD_REQUEST", {
        message: "Flow ZIP 不能为空",
        status: 400,
      });
    }
    if (stat.size > MAX_CLIENT_PACKAGE_BYTES) {
      throw new ORPCError("PAYLOAD_TOO_LARGE", {
        message: "Flow ZIP 超过客户端 64 MiB 安全上限",
        status: 413,
      });
    }

    try {
      const content = await fs.readFile(filePath);
      const upload = await uploadEngineFlowPackage({
        content: new Uint8Array(content),
        description: input.description,
        fileName,
        labels: input.labels,
        scope: input.scope,
      });
      return {
        cancelled: false as const,
        fileName,
        fileSize: stat.size,
        upload,
      };
    } catch (error) {
      return raiseEngineError(error);
    }
  });

export const validateFlowVersion = os
  .input(validateFlowVersionSchema)
  .handler(async ({ input }) => {
    try {
      return await validateEngineFlowVersion(input);
    } catch (error) {
      return raiseEngineError(error);
    }
  });

export const publishFlowVersion = os
  .input(publishFlowVersionSchema)
  .handler(async ({ input }) => {
    try {
      return await publishEngineFlowVersion(input);
    } catch (error) {
      return raiseEngineError(error);
    }
  });
