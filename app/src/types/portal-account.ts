import type { ClientOpenMode } from "@/types/web-tab";

export type PortalEntityType = "CUSTOMER" | "SUPPLIER";
export type PortalStatus = "ENABLED" | "DISABLED";
export type PortalCategory = "TIANDI" | "BOE";

export interface PortalAccount {
  id: string;
  tenantId: string;
  entityType: PortalEntityType;
  erpEntityCode: string;
  erpEntityName: string;
  businessEntity: string;
  ou: string;
  category: PortalCategory;
  portalName: string;
  portalUrl: string;
  loginAccount: string;
  clientOpenMode: ClientOpenMode;
  clientSessionPartition: string;
  status: PortalStatus;
  ownerUserId: string;
  ownerName: string;
  createdBy: string;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
}

export type CreatePortalAccountInput = Omit<
  PortalAccount,
  "id" | "tenantId" | "createdBy" | "createdAt" | "updatedAt"
> & {
  credentialRef?: string;
};

export type PortalOwnerCandidate = {
  userId: string;
  name: string;
  username?: string;
};

export type UpdatePortalAccountInput = Partial<
  Pick<
    PortalAccount,
    | "entityType"
    | "portalName"
    | "portalUrl"
    | "loginAccount"
    | "clientOpenMode"
    | "clientSessionPartition"
    | "status"
    | "erpEntityName"
    | "erpEntityCode"
    | "businessEntity"
    | "ou"
    | "category"
    | "ownerUserId"
    | "ownerName"
  >
> & {
  credentialRef?: string;
};
