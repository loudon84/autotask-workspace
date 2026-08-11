import { ApiClientError } from "@/actions/autotask-api";
import { apiRequest } from "@/services/api-client";
import { mapPortalAccount, mapPortalAccountList } from "@/services/dto-mappers";
import type {
  CreatePortalAccountInput,
  PortalAccount,
  UpdatePortalAccountInput,
} from "@/types/portal-account";

export async function listPortalAccounts(): Promise<PortalAccount[]> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: "/portal-accounts",
  });
  return mapPortalAccountList(data);
}

export async function getPortalAccount(
  id: string
): Promise<PortalAccount | undefined> {
  try {
    const data = await apiRequest<unknown>({
      method: "GET",
      path: `/portal-accounts/${id}`,
    });
    return mapPortalAccount(data);
  } catch (err) {
    if (err instanceof ApiClientError && err.status === 404) {
      return;
    }
    throw err;
  }
}

export async function createPortalAccount(
  input: CreatePortalAccountInput
): Promise<PortalAccount> {
  const data = await apiRequest<unknown>({
    method: "POST",
    path: "/portal-accounts",
    body: input,
  });
  return mapPortalAccount(data);
}

export async function updatePortalAccount(
  id: string,
  patch: UpdatePortalAccountInput
): Promise<PortalAccount> {
  const data = await apiRequest<unknown>({
    method: "PATCH",
    path: `/portal-accounts/${id}`,
    body: patch,
  });
  return mapPortalAccount(data);
}

export async function deletePortalAccount(id: string): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/portal-accounts/${id}`,
  });
}

export async function testOpenPortalAccount(
  id: string
): Promise<PortalAccount | undefined> {
  const data = await apiRequest<unknown>({
    method: "POST",
    path: `/portal-accounts/${id}/test-open`,
  });
  if (data === undefined || data === null) {
    return;
  }
  return mapPortalAccount(data);
}
