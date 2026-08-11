import z from "zod";

export const openUrlInputSchema = z.object({
  url: z.string(),
  title: z.string().optional(),
  sourceType: z.enum(["portal", "human_task", "manual_url"]),
  portalId: z.string().optional(),
  taskId: z.string().optional(),
  humanActionId: z.string().optional(),
  sessionPartition: z.string().optional(),
  openMode: z.enum(["webcontents", "system_browser"]).optional(),
});

export const tabIdInputSchema = z.object({
  tabId: z.string(),
});

export const openPortalInputSchema = z.object({
  portalId: z.string(),
  url: z.string(),
  title: z.string().optional(),
  sessionPartition: z.string(),
  openMode: z.enum(["webcontents", "system_browser"]).optional(),
});

export const openHumanTaskInputSchema = z.object({
  taskId: z.string(),
  humanActionId: z.string().optional(),
  url: z.string(),
  title: z.string().optional(),
  portalId: z.string().optional(),
  sessionPartition: z.string().optional(),
});

export const setBoundsInputSchema = z.object({
  x: z.number(),
  y: z.number(),
  width: z.number(),
  height: z.number(),
});

export const setVisibilityInputSchema = z.object({
  visible: z.boolean(),
});

export const clearSessionInputSchema = z.object({
  partition: z.string(),
});

export const openExternalInputSchema = z.object({
  url: z.string(),
});
