export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface PublicAuthUser {
  displayName: string;
  email: string;
  id: string;
}

export interface PublicAuthOrganization {
  id: string;
  name: string;
}

export interface PublicAuthState {
  organization?: PublicAuthOrganization;
  status: AuthStatus;
  user?: PublicAuthUser;
}
