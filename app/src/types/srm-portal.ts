import type { ClientOpenMode } from "@/types/web-tab";

/** @deprecated Use PortalAccount from @/types/portal-account */
export type PortalLoginState = "unknown" | "valid" | "expired";
export type PortalEntityType = "CUSTOMER" | "SUPPLIER" | "BOTH";

export interface CreatePortalAccountInput {
  clientOpenMode: ClientOpenMode;
  clientSessionPartition: string;
  credentialRef?: string;
  entityType: PortalEntityType;
  erpEntityCode: string;
  erpEntityName: string;
  loginAccount: string;
  portalName: string;
  portalUrl: string;
  status: SRMPortal["status"];
}

export type UpdatePortalAccountInput = Partial<CreatePortalAccountInput>;

/** @deprecated Use PortalAccount from @/types/portal-account */
export interface SRMPortal {
  clientOpenMode: ClientOpenMode;
  clientSessionPartition: string;

  createdAt: string;
  customerName: string;
  description?: string;
  entityType?: string;
  erpEntityCode?: string;
  fieldMapping?: Record<string, string>;
  id: string;
  lastLoginCheckedAt?: string;
  lastOpenedAt?: string;

  locatorProfile: Record<string, string>;
  loginAccount?: string;
  loginPageUrl?: string;

  loginState: PortalLoginState;

  loginType: "username_password" | "sso" | "manual";
  mfaPolicy?: string;
  name: string;

  serverRpaProfileId?: string;
  status: "enabled" | "disabled";
  tags?: string[];
  updatedAt: string;
  url: string;
}
