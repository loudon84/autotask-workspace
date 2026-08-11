import { z } from "zod";

export const flowScopeSchema = z.enum(["GLOBAL", "TENANT"]);

export const listFlowsSchema = z.object({
  scope: flowScopeSchema,
});

export const uploadFlowPackageSchema = z.object({
  description: z.string().max(5000).optional(),
  labels: z.array(z.string().trim().min(1).max(128)).max(50).optional(),
  scope: flowScopeSchema,
});

export const validateFlowVersionSchema = z.object({
  flowVersionId: z.uuid(),
  scope: flowScopeSchema,
});

export const publishFlowVersionSchema = z.object({
  flowVersionId: z.uuid(),
  reason: z.string().max(2000).optional(),
  scope: flowScopeSchema,
});
