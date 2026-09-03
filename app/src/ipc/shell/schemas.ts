import z from "zod";

export const INVOICE_FILE_EXTENSIONS = [
  "png",
  "jpg",
  "jpeg",
  "pdf",
  "ofd",
] as const;

export const CATEGORY_DOCUMENT_EXTENSIONS = [
  "doc",
  "docx",
  "pdf",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "txt",
  "zip",
] as const;

export const MAX_INVOICE_FILE_COUNT = 10;
export const MAX_INVOICE_FILE_BYTES = 20 * 1024 * 1024;

export const openExternalLinkInputSchema = z.object({
  url: z.url(),
});

export const downloadFileInputSchema = z.object({
  url: z.url(),
});
