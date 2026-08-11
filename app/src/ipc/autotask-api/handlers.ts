import { ORPCError } from "@orpc/server";
import { os } from "@orpc/server";
import {
  AutotaskApiError,
  requestAutotaskApi,
} from "@/main/autotask-api/autotask-api-client";
import { autotaskApiRequestSchema } from "./schemas";

export const request = os
  .input(autotaskApiRequestSchema)
  .handler(async ({ input }) => {
    try {
      return await requestAutotaskApi(input);
    } catch (err) {
      if (err instanceof AutotaskApiError) {
        throw new ORPCError("AUTOTASK_API_ERROR", {
          message: err.message,
          status: err.status,
          data: err.body,
        });
      }
      throw err;
    }
  });
