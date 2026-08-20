import { useMemo } from "react";
import { usePortalAccounts } from "@/features/srm-portals/api/use-portal-accounts";

/** portalAccountId → portalName（客户名） */
export function usePortalNameMap() {
  const { data: portals = [] } = usePortalAccounts();
  return useMemo(() => {
    const map = new Map<string, string>();
    for (const portal of portals) {
      map.set(portal.id, portal.portalName);
    }
    return map;
  }, [portals]);
}

export function resolvePortalCustomerName(
  portalNameMap: Map<string, string>,
  portalAccountId: string | null | undefined,
  fallback = "—"
): string {
  if (!portalAccountId) {
    return fallback;
  }
  return portalNameMap.get(portalAccountId)?.trim() || fallback;
}

/** portalAccountId → businessEntity（我方公司 / 交易主体） */
export function usePortalBusinessEntityMap() {
  const { data: portals = [] } = usePortalAccounts();
  return useMemo(() => {
    const map = new Map<string, string>();
    for (const portal of portals) {
      map.set(portal.id, portal.businessEntity ?? "");
    }
    return map;
  }, [portals]);
}

export function resolvePortalBusinessEntity(
  businessEntityMap: Map<string, string>,
  portalAccountId: string | null | undefined,
  fallback = "—"
): string {
  if (!portalAccountId) {
    return fallback;
  }
  const value = businessEntityMap.get(portalAccountId)?.trim();
  return value ? value : fallback;
}
