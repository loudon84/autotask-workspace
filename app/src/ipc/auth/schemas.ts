import { z } from "zod";

export const endpointConfigSchema = z.object({
  authBackendUrl: z.string().url(),
  authPrefix: z.string().min(1),
  rpaEngineUrl: z.string().url(),
  taskBackendUrl: z.string().url(),
  taskPrefix: z.string().min(1),
  aiosHomeUrl: z.string().url().optional(),
});

export const loginInputSchema = z.object({
  account: z.string().min(1),
  password: z.string().min(1),
});
