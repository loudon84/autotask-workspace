import z from "zod";

export const openExternalLinkInputSchema = z.object({
  url: z.url(),
});

export const downloadFileInputSchema = z.object({
  url: z.url(),
});
