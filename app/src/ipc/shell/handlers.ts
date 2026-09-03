import fs from "node:fs/promises";
import path from "node:path";
import { ORPCError, os } from "@orpc/server";
import { dialog, shell } from "electron";
import { ipcContext } from "@/ipc/context";
import {
  CATEGORY_DOCUMENT_EXTENSIONS,
  downloadFileInputSchema,
  INVOICE_FILE_EXTENSIONS,
  MAX_INVOICE_FILE_BYTES,
  MAX_INVOICE_FILE_COUNT,
  openExternalLinkInputSchema,
} from "./schemas";

export const openExternalLink = os
  .input(openExternalLinkInputSchema)
  .handler(({ input }) => {
    const { url } = input;
    shell.openExternal(url);
  });

export const downloadFile = os
  .input(downloadFileInputSchema)
  .use(ipcContext.mainWindowContext)
  .handler(({ context, input }) => {
    context.window.webContents.downloadURL(input.url);
  });

export const selectInvoiceFiles = os
  .use(ipcContext.mainWindowContext)
  .handler(async ({ context }) => {
    const selection = await dialog.showOpenDialog(context.window, {
      filters: [
        {
          extensions: [...INVOICE_FILE_EXTENSIONS],
          name: "发票文件",
        },
      ],
      properties: ["openFile", "multiSelections", "dontAddToRecent"],
      title: "选择发票",
    });
    if (selection.canceled || selection.filePaths.length === 0) {
      return { cancelled: true as const, files: [] };
    }
    if (selection.filePaths.length > MAX_INVOICE_FILE_COUNT) {
      throw new ORPCError("BAD_REQUEST", {
        message: `最多选择 ${MAX_INVOICE_FILE_COUNT} 个发票文件`,
        status: 400,
      });
    }

    const allowed = new Set<string>(INVOICE_FILE_EXTENSIONS);
    const files: Array<{ name: string; path: string; size: number }> = [];
    for (const filePath of selection.filePaths) {
      const ext = path.extname(filePath).slice(1).toLowerCase();
      if (!allowed.has(ext)) {
        throw new ORPCError("BAD_REQUEST", {
          message: `不支持的文件类型：${path.basename(filePath)}`,
          status: 400,
        });
      }
      const stat = await fs.stat(filePath);
      if (stat.size <= 0) {
        throw new ORPCError("BAD_REQUEST", {
          message: `${path.basename(filePath)} 是空文件`,
          status: 400,
        });
      }
      if (stat.size > MAX_INVOICE_FILE_BYTES) {
        throw new ORPCError("PAYLOAD_TOO_LARGE", {
          message: `${path.basename(filePath)} 超过 20MB`,
          status: 413,
        });
      }
      files.push({
        name: path.basename(filePath),
        path: filePath,
        size: stat.size,
      });
    }
    return { cancelled: false as const, files };
  });

export const selectCategoryDocumentFiles = os
  .use(ipcContext.mainWindowContext)
  .handler(async ({ context }) => {
    const selection = await dialog.showOpenDialog(context.window, {
      filters: [
        {
          extensions: [...CATEGORY_DOCUMENT_EXTENSIONS],
          name: "操作手册",
        },
      ],
      properties: ["openFile", "multiSelections", "dontAddToRecent"],
      title: "选择文档",
    });
    if (selection.canceled || selection.filePaths.length === 0) {
      return { cancelled: true as const, files: [] };
    }
    if (selection.filePaths.length > MAX_INVOICE_FILE_COUNT) {
      throw new ORPCError("BAD_REQUEST", {
        message: `最多选择 ${MAX_INVOICE_FILE_COUNT} 个文件`,
        status: 400,
      });
    }

    const allowed = new Set<string>(CATEGORY_DOCUMENT_EXTENSIONS);
    const files: Array<{ name: string; path: string; size: number }> = [];
    for (const filePath of selection.filePaths) {
      const ext = path.extname(filePath).slice(1).toLowerCase();
      if (!allowed.has(ext)) {
        throw new ORPCError("BAD_REQUEST", {
          message: `不支持的文件类型：${path.basename(filePath)}`,
          status: 400,
        });
      }
      const stat = await fs.stat(filePath);
      if (stat.size <= 0) {
        throw new ORPCError("BAD_REQUEST", {
          message: `${path.basename(filePath)} 是空文件`,
          status: 400,
        });
      }
      if (stat.size > MAX_INVOICE_FILE_BYTES) {
        throw new ORPCError("PAYLOAD_TOO_LARGE", {
          message: `${path.basename(filePath)} 超过 20MB`,
          status: 413,
        });
      }
      files.push({
        name: path.basename(filePath),
        path: filePath,
        size: stat.size,
      });
    }
    return { cancelled: false as const, files };
  });
