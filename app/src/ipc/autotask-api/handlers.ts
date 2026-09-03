import fs from "node:fs/promises";
import { ORPCError } from "@orpc/server";
import { os } from "@orpc/server";
import { dialog } from "electron";
import { ipcContext } from "@/ipc/context";
import {
  AutotaskApiError,
  fetchCategoryDocumentBytes,
  requestAutotaskApi,
  uploadCategoryDocumentFiles,
  uploadStatementInvoiceFiles,
} from "@/main/autotask-api/autotask-api-client";
import {
  autotaskApiRequestSchema,
  downloadCategoryDocumentInputSchema,
  uploadCategoryDocumentsInputSchema,
  uploadInvoiceFilesInputSchema,
} from "./schemas";

function toOrpcError(err: unknown): never {
  if (err instanceof AutotaskApiError) {
    throw new ORPCError("AUTOTASK_API_ERROR", {
      message: err.message,
      status: err.status,
      data: err.body,
    });
  }
  throw err;
}

export const request = os
  .input(autotaskApiRequestSchema)
  .handler(async ({ input }) => {
    try {
      return await requestAutotaskApi(input);
    } catch (err) {
      toOrpcError(err);
    }
  });

export const uploadInvoiceFiles = os
  .input(uploadInvoiceFilesInputSchema)
  .handler(async ({ input }) => {
    try {
      return await uploadStatementInvoiceFiles(input);
    } catch (err) {
      toOrpcError(err);
    }
  });

export const uploadCategoryDocuments = os
  .input(uploadCategoryDocumentsInputSchema)
  .handler(async ({ input }) => {
    try {
      return await uploadCategoryDocumentFiles(input);
    } catch (err) {
      toOrpcError(err);
    }
  });

export const downloadCategoryDocument = os
  .input(downloadCategoryDocumentInputSchema)
  .use(ipcContext.mainWindowContext)
  .handler(async ({ context, input }) => {
    try {
      const bytes = await fetchCategoryDocumentBytes({
        category: input.category,
        documentId: input.documentId,
      });
      const save = await dialog.showSaveDialog(context.window, {
        defaultPath: input.fileName,
        title: "保存文档",
      });
      if (save.canceled || !save.filePath) {
        return { cancelled: true as const };
      }
      await fs.writeFile(save.filePath, bytes);
      return { cancelled: false as const, path: save.filePath };
    } catch (err) {
      toOrpcError(err);
    }
  });
