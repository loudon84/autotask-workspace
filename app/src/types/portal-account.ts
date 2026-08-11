import type { ClientOpenMode } from "@/types/web-tab";

export type PortalEntityType = "CUSTOMER" | "SUPPLIER";
export type PortalStatus = "ENABLED" | "DISABLED";

export interface PortalAccount {
  id: string;
  tenantId: string;
  entityType: PortalEntityType;
  erpEntityCode: string;
  erpEntityName: string;
  portalName: string;
  portalUrl: string;
  loginAccount: string;
  clientOpenMode: ClientOpenMode;
  clientSessionPartition: string;
  status: PortalStatus;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export type CreatePortalAccountInput = Omit<
  PortalAccount,
  "id" | "tenantId" | "createdBy" | "createdAt" | "updatedAt"
> & {
  credentialRef?: string;
};

export type UpdatePortalAccountInput = Partial<
  Pick<
    PortalAccount,
    | "portalName"
    | "portalUrl"
    | "loginAccount"
    | "clientOpenMode"
    | "clientSessionPartition"
    | "status"
    | "erpEntityName"
    | "erpEntityCode"
  >
> & {
  credentialRef?: string;
};
