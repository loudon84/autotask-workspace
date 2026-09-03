import { z } from "zod";

export const autotaskApiRequestSchema = z.object({
  method: z.enum(["GET", "POST", "PATCH", "PUT", "DELETE"]),
  path: z.string().min(1),
  body: z.unknown().optional(),
  query: z
    .record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
    .optional(),
});

export const uploadInvoiceFilesInputSchema = z.object({
  billId: z.string().min(1),
  filePaths: z.array(z.string().min(1)).min(1).max(10),
});

export const uploadCategoryDocumentsInputSchema = z.object({
  category: z.string().min(1),
  filePaths: z.array(z.string().min(1)).min(1).max(10),
});

export const downloadCategoryDocumentInputSchema = z.object({
  category: z.string().min(1),
  documentId: z.string().min(1),
  fileName: z.string().min(1),
});
